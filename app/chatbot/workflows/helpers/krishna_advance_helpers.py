import asyncio
from collections.abc import AsyncGenerator
import json
from loguru import logger
import re


from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, AgentState, AgentThought
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
    if len(state.thoughts) == 0:
        return "thinker"
    elif any(thought.action.name == "final_response" for thought in state.thoughts):
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
        tasks = []
        for thought in state.thoughts:
            selected_tool_name = thought.action.name
            if selected_tool_name not in tools:
                logger.error(f"Unknown tool: {selected_tool_name}")
                raise ValueError(f"Unknown tool selected by the assistant: {selected_tool_name}")

            selected_tool = tools[selected_tool_name]
            tasks.append(asyncio.create_task(selected_tool(state=state)))

        observations = await asyncio.gather(*tasks, return_exceptions=False)
        observations = list(filter(bool, observations))

        logger.info(f"Got the observations: {observations}")
        state.observations.extend(observations)

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
Provide response in JSON Format ONLY using following structure including the ```json ```:
```json
{json.dumps(AgentThought.model_json_schema())}
```

# EXAMPLE OUTPUT

```json
{
            AgentThought(
                thought="To solve this problem, I would need to implement a python code. Let's use `python_runner`",
                action=Action(name="python_runner", params={"code_snippet": "print(54 * 100)"}),
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
"""
        logger.info("Sending Initial Prompt...\n")
        state.prompt = prompt
        return state

    def validate_response(self, state: AgentState) -> AgentState:
        logger.info(f"Validating Response\n\n{state.draft_response}")
        plan_of_action = state.draft_response
        try:
            parsed_json = extract_json_block(plan_of_action.strip())
            thought = AgentThought.model_validate_json(parsed_json)
            logger.info(f"Plan of action\n{thought.model_dump_json()}")
            state.thoughts = [thought]
        except json.JSONDecodeError as e:
            state.retry += 1
            state.prompt += f"\n Failed to parse the response: {e}. Stick to the format instructions"
            logger.error(f"Failed to parse plan JSON: {e}. Falling back to raw parse.")
            if state.retry == 2:
                raise ValueError("Failed to parse the plan of action after multiple retries.")
            return state

        return state
