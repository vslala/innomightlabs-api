from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import json
from loguru import logger
import re


from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, ActionResult, AgentMessage, AgentState, AgentThought, Phase, StreamChunk, StreamStep
from app.chatbot.workflows.prompts.system.intuitive_knowledge import INTUITIVE_KNOWLEDGE
from app.common.models import Role


def write_to_file(filepath: str, content: str) -> None:
    """
    Write content to a file, creating directories if they don't exist.
    """
    import os

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    logger.info(f"Content written to {filepath}")


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

    def _check_duplicate_tool_call(self, state: AgentState) -> bool:
        """Check if the same tool is being called with identical parameters"""
        import hashlib
        import json

        if not state.thought or not state.last_tool_call:
            return False

        current_tool = state.thought.action.name
        current_params = json.dumps(state.thought.action.params, sort_keys=True)
        current_hash = hashlib.md5(current_params.encode()).hexdigest()

        last_tool, last_hash = state.last_tool_call
        return current_tool == last_tool and current_hash == last_hash

    async def thinker(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        plan_of_action = ""
        async for chunk in self.chatbot.stream_response(prompt=state.prompt):
            plan_of_action += str(chunk)

        state.llm_response = plan_of_action
        yield state

    def prompt_builder(self, state: AgentState) -> AgentState:
        """
        Build the prompt for the LLM with MemoryManagerV2 integration
        """
        prompt = {
            "system_prompt": INTUITIVE_KNOWLEDGE,
            "current_time": datetime.now(timezone.utc).isoformat(),
            "archival_memory": state.memory_blocks,
            "recalled_memory": state.build_conversation_context(),
            "conversation_history": state.build_conversation_history(),
            "heartbeats_used": state.epochs,
            "current_user_query": state.user_message,
        }

        state.prompt = json.dumps(prompt, indent=2)
        logger.info(f"Prompt built for epoch {state.epochs}")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        write_to_file(f"/tmp/prompts/prompt_{state.epochs}.md", state.prompt)
        logger.debug(f"Prompt:\n{state.prompt}")
        return state

    def parse_actions(self, state: AgentState) -> AgentState:
        import yaml

        state.epochs += 1
        logger.info(f"Validating Response\n\n{state.llm_response}...")
        plan = state.llm_response

        try:
            # ——— 1) inner_monologue handling unchanged ———
            thoughts = deque([])
            for monologue in extract_tag_content(plan, "inner_monologue") or []:
                text = monologue.strip()
                state.stream_queue.put_nowait(StreamChunk(content=text, step=StreamStep.PLANNING, step_title="Reflecting..."))
                thoughts.append(text)
                # state.stream_queue.put_nowait(StreamChunk(content=text, step=StreamStep.PLANNING, step_title="Reflecting..."))

            for idx, action in enumerate(extract_tag_content(plan, "action")) or []:
                action = action.strip()
                action = yaml.safe_load(action)
                action = Action.model_validate(action)
                state.thoughts.append(AgentThought(thought=thoughts[idx], action=action))

            write_to_file(f"/tmp/prompts/response_{state.epochs}.md", plan)

        except Exception as e:
            state.retry += 1
            logger.error(f"Validation failed: {e}. Retry: {state.retry}")
            state.messages.append(AgentMessage(message=f"Validation failed while parsing your yaml response: {e}", role=Role.SYSTEM))
            raise ValueError(f"Validation failed while parsing your yaml response: {e}") from e

        return state

    async def execute_actions(self, state: AgentState) -> AgentState:
        """Execute the actions in the plan"""
        import app.chatbot.workflows.helpers.tools as Tools
        import hashlib
        import json

        logger.info("\n\nExecuting Actions...\n\n")

        while state.thoughts:
            thought = state.thoughts.popleft()
            action = thought.action
            selected_tool_name = action.name
            if selected_tool_name not in Tools.new_tools:
                logger.error(f"Unknown tool: {selected_tool_name}")
                state.phase = Phase.ERROR
                return state

            selected_tool = Tools.new_tools[selected_tool_name]
            input_params = action.params

            # Update last tool call tracking
            params_hash = hashlib.md5(json.dumps(input_params, sort_keys=True).encode()).hexdigest()
            state.last_tool_call = (selected_tool_name, params_hash)

            # Handle LangChain tools vs custom async functions differently
            if hasattr(selected_tool, "args_schema") and hasattr(selected_tool, "invoke"):
                # LangChain tool - create proper input object with thought from state
                tool_params = {"thought": thought, **input_params}
                tool_input = selected_tool.args_schema(**tool_params)
                # LangChain tools expect state and input as separate arguments to the underlying function
                response = await selected_tool.coroutine(state, tool_input)
                state.observations.append(response)
                if selected_tool_name == "send_message":
                    state.phase = Phase.NEED_FINAL
                    state.observations = []
                    state.epochs = 0
                    break
                elif action.request_heartbeat:
                    action_result = ActionResult.model_validate(response)
                    state.messages.append(AgentMessage(message=thought.action.model_dump_json(), role=Role.ASSISTANT))
                    state.messages.append(AgentMessage(message=action_result.result, role=Role.USER))
                    state.phase = Phase.NEED_TOOL
                    break
                else:
                    state.phase = Phase.ERROR
                    break
            else:
                # Custom async function
                response = await selected_tool(state)
                state.observations.append(response)
                state.phase = Phase.NEED_FINAL

        logger.debug(f"NEXT PHASE: {state.phase}")
        return state

    async def final_response(self, state: AgentState) -> AgentState:
        """Generate the final response based on the plan and user message"""
        prompt = {
            "system_prompt": "You are Krishna! Answer user's query in the best and concise and friendly way possible.",
            "conversation_history": state.build_conversation_history(),
            "current_user_query": state.user_message,
        }

        async for chunk in self.chatbot.stream_response(prompt=json.dumps(prompt, indent=2)):
            await state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.FINAL_RESPONSE, step_title="Sending response..."))

        return state

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
