from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import json
from loguru import logger

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, ActionResult, SingleMessage, AgentState, AgentThought, Phase, StreamChunk, StreamStep
from app.chatbot.components.conversation_manager import ConversationManager
from app.chatbot.workflows.prompts.system.intuitive_knowledge import INTUITIVE_KNOWLEDGE
from app.common.models import Role
from app.common.utils import extract_tag_content, write_to_file


class KrishnaAdvanceWorkflowHelper:
    def __init__(self, chatbot: BaseChatbot, conversation_manager: ConversationManager) -> None:
        self.chatbot = chatbot
        self.conversation_manager = conversation_manager

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

    async def prompt_builder(self, state: AgentState) -> AgentState:
        """
        Build the prompt for the LLM with MemoryManagerV2 integration
        """
        prompt = {
            "system_prompt": INTUITIVE_KNOWLEDGE,
            "current_time": datetime.now(timezone.utc).isoformat(),
            "archival_memory": [v.serialize() for k, v in state.memory_blocks.items()],
            "recalled_memory": state.build_conversation_context(),
            "conversation_history": [SingleMessage.from_message(m).model_dump_json() for m in await self.conversation_manager.get_messages()],
            "heartbeats_used": state.epochs,
            "current_user_query": state.user_message,
        }

        if state.epochs > 10:
            prompt.update({"CRITICAL": f"TOO MANY HEART BEATS USED (>{state.epochs}). RESPOND TO USER ASAP."})

        state.prompt = json.dumps(prompt, indent=2, default=str)
        logger.info(f"Prompt built for epoch {state.epochs}")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        write_to_file(f"/tmp/prompts/prompt_{state.epochs}.md", state.prompt)
        logger.debug(f"Prompt:\n{state.prompt}")
        return state

    async def thinker(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        plan_of_action = ""
        async for chunk in self.chatbot.stream_response(prompt=state.prompt):
            plan_of_action += str(chunk)

        state.llm_response = plan_of_action
        yield state

    async def parse_actions(self, state: AgentState) -> AgentState:
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
            await self.conversation_manager.append_message(SingleMessage(message=f"Validation failed while parsing your yaml response: {e}", role=Role.SYSTEM))
            raise ValueError(f"Validation failed while parsing your yaml response: {e}") from e

        return state

    async def execute_actions(self, state: AgentState) -> AgentState:
        """Execute the actions in the plan"""
        import app.chatbot.components.tools as Tools
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
                response = ActionResult.model_validate(await selected_tool.coroutine(state, tool_input))
                state.observations.append(response)
                if selected_tool_name == "send_message":
                    await self.conversation_manager.append_message(SingleMessage(message=response.result, role=Role.ASSISTANT))
                    state.phase = Phase.NEED_FINAL
                    state.observations = []
                    state.epochs = 0
                    break
                elif action.request_heartbeat:
                    action_result = ActionResult.model_validate(response)
                    await self.conversation_manager.append_message(SingleMessage(message=thought.action.model_dump_json(), role=Role.ASSISTANT))
                    await self.conversation_manager.append_message(SingleMessage(message=action_result.result, role=Role.USER))
                    state.phase = Phase.NEED_TOOL
                    break
                else:
                    state.phase = Phase.ERROR
                    break
            else:
                # Custom async function
                response = await selected_tool.func(state)
                state.observations.append(response)
                state.phase = Phase.NEED_FINAL

        logger.debug(f"NEXT PHASE: {state.phase}")
        return state

    async def manage_conversations(self, state: AgentState) -> AgentState:
        """Manage the conversation history"""
        await self.conversation_manager.handle_messages()
        return state

    async def final_response(self, state: AgentState) -> AgentState:
        """Generate the final response based on the plan and user message"""
        # Limit conversation history to last 5 messages to avoid context overflow
        messages = await self.conversation_manager.get_messages()
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        conversation_history = "\n".join([f"[{m.role.value}]: {m.content}" for m in recent_messages])

        prompt = {
            "system_prompt": "You are Krishna! Answer user's query in the best and concise and friendly way possible.",
            "conversation_history": conversation_history,
            "current_user_query": state.user_message,
        }

        async for chunk in self.chatbot.stream_response(prompt=json.dumps(prompt, indent=2)):
            await state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.FINAL_RESPONSE, step_title="Sending response..."))

        return state

    async def persist_message_exchange(self, state: AgentState) -> AgentState:
        """Persist the message exchange"""
        await self.conversation_manager.handle_final_response()
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
