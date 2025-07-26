from collections.abc import AsyncGenerator
import json
from loguru import logger
import re


from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, AgentState, AgentThought, Phase, StreamChunk, StreamStep
from app.chatbot.workflows.helpers.tools import (
    available_actions,
    tools,
)


JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_block(text: str) -> str:
    """
    Extracts the first JSON array block wrapped in triple backticks.
    """
    match = JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    else:
        raise ValueError("Cannot parse the provided content")


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
        logger.info("\n\nExecuting Actions...\n\n")
        if not state.thought:
            raise ValueError("No thought provided")

        selected_tool_name = state.thought.action.name
        if selected_tool_name not in tools:
            logger.error(f"Unknown tool: {selected_tool_name}")
            raise ValueError(f"Unknown tool selected by the assistant: {selected_tool_name}")

        selected_tool = tools[selected_tool_name]
        result = await selected_tool(state=state)
        state.observations.append(result)

        logger.info(f"Got the observations: {result}")
        state.thought = None
        yield state

    async def thinker(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        plan_of_action = ""
        async for chunk in self.chatbot.stream_response(prompt=state.prompt):
            plan_of_action += str(chunk)

        state.draft_response = plan_of_action
        yield state

    def prompt_builder(self, state: AgentState) -> AgentState:
        prompt = f"""
# SYSTEM INSTRUCTIONS

You are a genius supercomputer called “Krishna” who performs tasks to answer user's query in the best possible way. You have access to tools which you can use to perform tasks.
Provide response in proper JSON Format that can be parsed by pydantic only using following structure including the ```json ```:
```json
{json.dumps(AgentThought.model_json_schema())}
```

# EXAMPLE OUTPUT

```json
{
            AgentThought(
                thought="To solve this problem, I would need to implement a python code. Let's use `python_runner`",
                action=Action(name="python_runner", params={"code_snippet": "<provide the code directly in text>"}),
            ).model_dump_json()
        }
```

# AVAILABLE ACTIONS

{json.dumps([action.model_dump_json() for action in available_actions])}

# CONVERSATION HISTORY
{state.build_conversation_history()}

# CURRENT USER QUERY
"{state.user_message}"

IMPORTANT: ONLY RESPOND IN JSON USING ABOVE TOOLS
Your job is to answer user's query in the best way possible. 

Check for the answers in the result of your previous actions first.

{state.build_observation()}

{state.get_error_message()}
"""
        logger.info("Sending Initial Prompt...\n")
        logger.info(f"Observations\n{state.build_observation()}")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        state.prompt = prompt
        return state

    def validate_response(self, state: AgentState) -> AgentState:
        logger.info(f"Validating Response\n\n{state.draft_response}")
        plan_of_action = state.draft_response
        try:
            parsed_json = extract_json_block(plan_of_action.strip())
            loaded_obj = json.loads(parsed_json, strict=False)
            thought = AgentThought.model_validate(loaded_obj)
            logger.info(f"Plan of action\n{thought.model_dump_json()}")
            state.thought = thought
            state.phase = Phase.NEED_FINAL if thought.action.name == "final_response" else Phase.NEED_TOOL
        except json.JSONDecodeError as e:
            state.phase = Phase.NEED_FINAL
            state.retry += 1
            state.error_message = f"\n Failed to parse your Thought: {e}"
            logger.error(f"Failed to parse plan JSON: {e}. Falling back to raw parse.")
            if state.retry == 2:
                raise ValueError("Failed to parse the plan of action after multiple retries.")
            return state

        return state

    async def final_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Generate the final response based on the plan and user message.
        """
        final_response = state.thought.action.params.get("text", "") if state.thought else ""
        await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))

        state.draft_response = final_response
        yield state
