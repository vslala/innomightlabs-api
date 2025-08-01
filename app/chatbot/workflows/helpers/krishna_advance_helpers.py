from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from loguru import logger
import re


from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, AgentMessage, AgentState, AgentThought, Phase, StreamChunk, StreamStep
from app.chatbot.workflows.prompts.system.base_prompt import BASE_PROMPT
from app.chatbot.workflows.prompts.system.intuitive_knowledge import INTUITIVE_KNOWLEDGE
from app.common.models import Role


# Only match the FIRST JSON block to prevent infinite loops
JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def write_to_file(filepath: str, content: str) -> None:
    """
    Write content to a file, creating directories if they don't exist.
    """
    import os

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    logger.info(f"Content written to {filepath}")


def extract_json_block(text: str) -> str:
    """
    Extracts ONLY the FIRST JSON block and logs if multiple blocks exist.
    This aggressively prevents infinite loops.
    """
    matches = JSON_BLOCK_RE.findall(text)
    if not matches:
        raise ValueError("No JSON block found in the response.")

    if len(matches) > 1:
        logger.warning(f"INFINITE LOOP PREVENTION: Found {len(matches)} JSON blocks, using only the first one")

    json_content = matches[0].strip()
    return json_content


def extract_tag_content(text: str, tag: str) -> list[str]:
    """
    Extracts all text contents inside provided tag.
    """
    esc = re.escape(tag)
    pattern = rf"<{esc}>(.*?)</{esc}>"
    return re.findall(pattern, text, flags=re.DOTALL)


def route_condition(state: AgentState) -> str:
    """
    Determine if the final response action is present in the thoughts.
    """
    if not state.thought:
        return "thinker"
    elif state.thought.action.name == "final_response":
        return "final_response"
    return "router"


class KrishnaAdvanceWorkflowHelper:
    def __init__(self, chatbot: BaseChatbot) -> None:
        self.chatbot = chatbot

    async def router(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Execute the actions in the plan.
        This method processes each action in the plan and executes it.
        """
        import app.chatbot.workflows.helpers.tools as Tools

        logger.info("\n\nExecuting Actions...\n\n")
        if not state.thought:
            raise ValueError("No thought provided")

        selected_tool_name = state.thought.action.name
        if selected_tool_name not in Tools.new_tools:
            logger.error(f"Unknown tool: {selected_tool_name}")
            raise ValueError(f"Unknown tool selected by the assistant: {selected_tool_name}")

        selected_tool = Tools.new_tools[selected_tool_name]

        input_params = state.thought.action.params

        # Handle LangChain tools vs custom async functions differently
        if hasattr(selected_tool, "args_schema") and hasattr(selected_tool, "invoke"):
            # LangChain tool - create proper input object with thought from state
            tool_params = {"thought": state.thought.thought, **input_params}
            tool_input = selected_tool.args_schema(**tool_params)
            # LangChain tools expect state and input as separate arguments to the underlying function
            result = await selected_tool.coroutine(state, tool_input)
        else:
            # Custom async function
            result = await selected_tool(state)

        state.observations.append(result)
        state.messages.append(
            AgentMessage(
                message=result.result,
                role=Role.TOOL,
                timestamp=result.timestamp,
            )
        )

        logger.info(f"Got the observations: {result}")
        state.thought = None
        yield state

    async def thinker(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        plan_of_action = ""
        async for chunk in self.chatbot.stream_response(prompt=state.prompt):
            plan_of_action += str(chunk)

        state.llm_response = plan_of_action
        yield state

    def prompt_builder(self, state: AgentState) -> AgentState:
        """
        Build the prompt for the LLM with circuit breaker
        """
        # Check for memory overflow alerts
        memory_alert = state.get_memory_overflow_alert()
        memory_alert_text = f"\n{memory_alert}\n" if memory_alert else ""

        prompt = f"""
{BASE_PROMPT}

{INTUITIVE_KNOWLEDGE}

{memory_alert_text}

============ ARCHIVAL MEMORY BLOCKS ==================
{state.build_archival_memory()}
============ END OF ARCHIVAL MEMORY BLOCKS ===============

============ RECALL MEMORY BLOCKS ===================
{state.build_recall_memory()}
============ END OF RECALL MEMORY BLOCKS ================

============ CONVERSATION HISTORY ==================
{state.build_conversation_history()}
============ END OF CONVERSATION HISTORY ===============

Current User Query:
[user - ({datetime.now(timezone.utc).isoformat()})] - {state.user_message}

"""
        state.prompt = state.build_prompt(prompt=prompt)
        logger.info(f"Prompt built for epoch {state.epochs}")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        write_to_file(f"/tmp/prompts/prompt_{state.epochs}.md", state.prompt)
        logger.debug(f"\n==== CONVERSATION HISTORY ====\n\n{state.build_conversation_history()}\n")
        logger.debug(f"\n==== ARCHIVAL MEMORY ====\n{state.build_archival_memory()}\n")
        logger.debug(f"\nObservations\n{state.build_observations()}")
        return state

    def validate_response(self, state: AgentState) -> AgentState:
        import yaml

        logger.info(f"Validating Response\n\n{state.llm_response}...")
        plan = state.llm_response

        try:
            # ——— 1) inner_monologue handling unchanged ———
            thoughts = ""
            for monologue in extract_tag_content(plan, "inner_monologue") or []:
                text = monologue.strip()
                thoughts += text + "\n"
                state.stream_queue.put_nowait(StreamChunk(content=text, step=StreamStep.PLANNING, step_title="Reflecting..."))

            # ——— 2) extract raw YAML block ———
            snippets = extract_tag_content(plan, "action")
            if not snippets:
                state.phase = Phase.NEED_TOOL
                return state
            raw_action = snippets[0]

            # ——— 3) parse YAML ———
            action_dict = yaml.safe_load(raw_action)

            # ——— 4) validate & assign ———
            agent_action = Action.model_validate(action_dict)
            state.thought = AgentThought(thought=thoughts, action=agent_action)
            state.phase = Phase.NEED_FINAL if agent_action.name == "send_message" else Phase.NEED_TOOL
            state.retry = 0
            write_to_file(f"/tmp/prompts/response_{state.epochs}.md", plan)

        except Exception as e:
            # ——— existing retry/fallback logic ———
            state.retry += 1
            logger.error(f"Validation failed: {e}. Retry: {state.retry}")
            state.messages.append(AgentMessage(message=f"Validation failed while parsing your yaml response: {e}", role=Role.SYSTEM))

            if state.retry >= 2:
                logger.warning("Forcing final response after multiple validation failures")
                state.thought = AgentThought(
                    thought="Validation failed multiple times, providing fallback response",
                    action=Action(
                        name="send_message",
                        description="Sends the message to the user",
                        params={"message": ("I apologize, but I'm having trouble processing your request. Please try rephrasing your question.")},
                    ),
                )
                state.phase = Phase.NEED_FINAL
            else:
                state.thought = None
                state.phase = Phase.NEED_TOOL

            return state

        return state

    async def final_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Generate the final response based on the plan and user message.
        """
        if not state.thought:
            raise ValueError("No thought provided for final_response")

        # Handle send_message action
        if state.thought.action.name == "send_message":
            final_response = state.thought.action.params.get("message", "")
        else:
            final_response = state.thought.action.params.get("text", "")

        if not final_response:
            raise ValueError(f"No message content found in {state.thought.action.name} action params")

        await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))

        state.llm_response = final_response
        yield state

    def _is_duplicate_action(self, state: AgentState, thought: AgentThought) -> bool:
        """Check if this action was already performed successfully"""
        if not state.observations:
            return False

        # Check last few observations for successful python_code_runner
        for obs in state.observations[-3:]:
            if obs.action == "python_runner" and thought.action.name == "python_code_runner" and "stdout" in obs.result:
                return True
        return False

    def _generate_final_response_from_observations(self, state: AgentState) -> str:
        """Generate final response based on observations"""
        if not state.observations:
            return "I couldn't complete the task."

        # Find the last successful python execution
        for obs in reversed(state.observations):
            if obs.action == "python_runner" and "stdout" in obs.result:
                try:
                    result_dict = eval(obs.result)
                    output = result_dict.get("stdout", "").strip()
                    if output:
                        return f"Here's the solution:\n\n{output}"
                except Exception:
                    pass

        return "I have processed your request but couldn't generate a clear output."
