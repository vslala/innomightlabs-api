from collections import defaultdict, deque
from datetime import datetime, timezone
import json
from loguru import logger

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import ActionResult, SingleMessage, AgentState, AgentThought, Phase, StreamChunk, StreamStep
from app.chatbot.components.conversation_manager import ConversationManager
from app.chatbot.components.tools import conversation_search, mcp_tools, memory_tools_v3, python_code_runner, send_message
from app.chatbot.components.tools_manager import ToolCategory, ToolsManager
from app.chatbot.workflows.prompts.system.intuitive_knowledge import get_intuitive_knowledge
from app.common.models import MemoryBlock, MemoryManagementConfig, MemoryType, Role
from app.common.utils import extract_tag_content, write_to_file
from app.common.workflows import BaseWorkflowHelper


class KrishnaAdvanceWorkflowHelper(BaseWorkflowHelper):
    def __init__(self, chatbot: BaseChatbot, conversation_manager: ConversationManager, tools_manager: ToolsManager) -> None:
        super().__init__(chatbot, conversation_manager, tools_manager)
        for tool in memory_tools_v3.memory_tools_v3:
            tools_manager.register_tool(ToolCategory.MEMORY, tool)
        for tool in mcp_tools.mcp_actions:
            tools_manager.register_tool(ToolCategory.MCP, tool)

        tools_manager.register_tool(ToolCategory.CORE, conversation_search)
        tools_manager.register_tool(ToolCategory.CORE, send_message)
        tools_manager.register_tool(ToolCategory.CODE, python_code_runner)

    async def prompt_builder(self, state: AgentState) -> AgentState:
        """
        Build the prompt for the LLM with MemoryManagerV2 integration
        """
        available_tools = defaultdict(list[dict])
        for cat, actions in self.tools_manager.get_tools_schema().items():
            available_tools[cat] = [item.model_dump() for item in actions]

        prompt = [
            MemoryBlock(
                title="System Instructions",
                type=MemoryType.SYSTEM,
                size=MemoryManagementConfig.SYSTEM_INSTRUCTIONS_SIZE,
                content=json.dumps(
                    {
                        "system_prompt": {
                            "intuitive_knowledge": get_intuitive_knowledge(),
                            "available_memory_types": [label.value for label in MemoryType],
                            "available_actions": available_tools,
                            "output": {
                                "critical_format_rules": self.tools_manager.format_rules,
                                "format_name": self.tools_manager.format_name,
                                "output_format": self.tools_manager.output_format_instructions,
                                "output_examples": self.tools_manager.output_examples,
                            },
                        },
                        "current_time_in_utc": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            ).model_dump(),
            MemoryBlock(
                title="Working Context",
                type=MemoryType.ARCHIVAL,
                size=MemoryManagementConfig.WORKING_CONTEXT_SIZE,
                content=json.dumps(
                    {
                        "archival_memory": [v.serialize() for k, v in state.memory_blocks.items()],
                        "recalled_memory": state.build_conversation_context(),
                    }
                ),
            ).model_dump(),
            MemoryBlock(
                title="Conversation History",
                type=MemoryType.CONVERSATION_HISTORY,
                size=MemoryManagementConfig.CONVERSATION_HISTORY_SIZE,
                content=json.dumps(
                    {
                        "conversation_history": [
                            SingleMessage.from_message(m).model_dump_json()
                            for m in await self.conversation_manager.get_messages(user=state.user, conversation_id=state.conversation_id)
                        ],
                    }
                ),
            ).model_dump(),
            {
                "heartbeats_used": state.epochs,
                "current_user_query": state.user_message,
            },
        ]

        if state.epochs > 20:
            prompt[-1].update({"CRITICAL": f"TOO MANY HEART BEATS USED (>{state.epochs}). RESPOND TO USER ASAP."})

        state.prompt = json.dumps(prompt, indent=2, default=str)
        logger.info(f"Prompt built for epoch {state.epochs}")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        write_to_file(f"/tmp/prompts/prompt_{state.epochs}.md", state.prompt)
        logger.debug(f"Prompt:\n{state.prompt}")
        return state

    async def thinker(self, state: AgentState) -> AgentState:
        import asyncio
        from botocore.exceptions import EventStreamError

        plan_of_action = ""
        try:
            async for chunk in self.chatbot.stream_response(prompt=state.prompt):
                plan_of_action += str(chunk)
        except EventStreamError as e:
            if "throttlingException" in str(e):
                logger.warning("Throttling exception encountered, waiting 10 seconds before retry")
                await asyncio.sleep(10)
                async for chunk in self.chatbot.stream_response(prompt=state.prompt):
                    plan_of_action += str(chunk)
            else:
                raise

        state.llm_response = plan_of_action
        return state

    async def parse_actions(self, state: AgentState) -> AgentState:
        state.epochs += 1
        logger.info(f"Validating Response (Epoch {state.epochs})")
        logger.info(f"Full Response:\n{state.llm_response}")
        plan = state.llm_response

        try:
            # ——— 1) Extract inner_monologue sections ———
            thoughts = deque([])
            monologue_blocks = extract_tag_content(plan, "inner_monologue") or []

            for monologue in monologue_blocks:
                text = monologue.strip()
                state.stream_queue.put_nowait(StreamChunk(content=text, step=StreamStep.PLANNING, step_title="Reflecting..."))
                thoughts.append(text)

            # ——— 2) Extract and parse action blocks ———
            action_blocks = extract_tag_content(plan, "action") or []

            if not action_blocks:
                logger.warning("No action blocks found in response!")

            for idx, action_block in enumerate(action_blocks):
                if idx >= len(thoughts):
                    # Ensure we have enough thoughts to pair with actions
                    logger.info(f"Adding empty thought for action {idx + 1} (no matching monologue)")
                    thoughts.append("")

                logger.info(f"Parsing action block {idx + 1} using {self.tools_manager.format_name} format")
                action_with_tags = f"<action>\n{action_block}\n</action>"
                parsed_actions = await self.tools_manager.parse_tool_calls(action_with_tags)
                logger.info(f"Parsed {len(parsed_actions)} actions from block {idx + 1}")

                for action_idx, action in enumerate(parsed_actions):
                    if action:
                        logger.info(f"Adding action: {action.name} to thoughts queue")
                        state.thoughts.append(AgentThought(thought=thoughts[idx], action=action))
                    else:
                        logger.warning(f"Skipping None action at index {action_idx}")

            logger.info(f"Total thoughts with actions: {len(state.thoughts)}")

        except Exception as e:
            state.retry += 1
            logger.error(f"Validation failed: {e}. Retry: {state.retry}")
            logger.exception("Detailed exception info:")
            format_name = getattr(self.tools_manager, "format_name", "response")
            await self.conversation_manager.append_message(
                conversation_id=state.conversation_id, message=SingleMessage(message=f"Validation failed while parsing your {format_name} response: {e}", role=Role.SYSTEM)
            )
            raise ValueError(f"Validation failed while parsing your {format_name} response: {e}") from e

        return state

    async def execute_actions(self, state: AgentState) -> AgentState:
        """Execute the actions in the plan"""
        import hashlib
        import json

        logger.info("\n\nExecuting Actions...\n\n")
        logger.info(f"Number of thoughts to process: {len(state.thoughts)}")

        while state.thoughts:
            thought = state.thoughts.popleft()
            action = thought.action

            logger.info(f"Processing action: {action.name} with params: {action.params}")
            logger.info(f"Request heartbeat: {action.request_heartbeat}")

            # Update last tool call tracking
            params_hash = hashlib.md5(json.dumps(action.params, sort_keys=True).encode()).hexdigest()
            state.last_tool_call = (action.name, params_hash)

            try:
                # Use the tools manager to execute the tool
                logger.info(f"Executing tool: {action.name}")
                response = await self.tools_manager.execute_tool(state, thought)
                logger.info(f"Tool execution result type: {type(response).__name__}")
                state.observations.append(response)

                # Handle special cases based on the tool and response
                if action.name == "send_message":
                    logger.info(f"Handling send_message action with response: {response.result}")
                    await self.conversation_manager.append_message(conversation_id=state.conversation_id, message=SingleMessage(message=response.result, role=Role.ASSISTANT))
                    logger.info("Message appended to conversation")
                    state.phase = Phase.NEED_FINAL
                    state.observations = []
                    state.epochs = 0
                    logger.info("Phase set to NEED_FINAL after send_message")
                    break
                elif action.request_heartbeat:
                    logger.info("Handling action with heartbeat request")
                    # Ensure response is an ActionResult
                    action_result = ActionResult.model_validate(response) if not isinstance(response, ActionResult) else response

                    # Log the action and result in the conversation
                    await self.conversation_manager.append_message(
                        conversation_id=state.conversation_id, message=SingleMessage(message=thought.action.model_dump_json(), role=Role.ASSISTANT)
                    )
                    await self.conversation_manager.append_message(conversation_id=state.conversation_id, message=SingleMessage(message=action_result.result, role=Role.USER))
                    state.phase = Phase.NEED_TOOL
                    logger.info("Phase set to NEED_TOOL for heartbeat action")
                    break
                else:
                    logger.warning(f"Action {action.name} has no heartbeat and is not `send_message`")
                    state.phase = Phase.ERROR
                    break

            except Exception as e:
                logger.error(f"Error executing action: {e}")
                logger.exception("Detailed exception info:")
                state.phase = Phase.NEED_TOOL
                await self.conversation_manager.append_message(conversation_id=state.conversation_id, message=SingleMessage(message=f"Error executing action: {e}", role=Role.USER))
                break

        await self.conversation_manager.handle_messages()
        logger.info(f"NEXT PHASE: {state.phase}")
        return state

    async def error_handler(self, state: AgentState) -> AgentState:
        """Generate the final response based on the plan and user message"""
        # Limit conversation history to last 5 messages to avoid context overflow
        messages = await self.conversation_manager.get_messages(user=state.user, conversation_id=state.conversation_id)
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        conversation_history = "\n".join([f"[{m.role.value}]: {m.content}" for m in recent_messages])

        prompt = {
            "system_prompt": "You are Krishna! Answer user's query in the best and concise and friendly way possible.",
            "conversation_history": conversation_history,
            "current_user_query": state.user_message,
        }

        final_message = ""
        async for chunk in self.chatbot.stream_response(prompt=json.dumps(prompt, indent=2)):
            await state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.FINAL_RESPONSE, step_title="Sending response..."))
            final_message += str(chunk)

        await self.conversation_manager.append_message(conversation_id=state.conversation_id, message=SingleMessage(message=final_message, role=Role.ASSISTANT))
        await self.conversation_manager.handle_final_response(user=state.user, conversation_id=state.conversation_id, current_user_message=state.user_message)

        return state

    async def persist_message_exchange(self, state: AgentState) -> AgentState:
        """Persist the message exchange"""
        await self.conversation_manager.handle_final_response(user=state.user, conversation_id=state.conversation_id, current_user_message=state.user_message)
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
