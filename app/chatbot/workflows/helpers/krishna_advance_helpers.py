from collections.abc import AsyncGenerator
import json
from loguru import logger
import re


from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import Action, ActionResult, AgentState, AgentThought, Phase, StreamChunk, StreamStep
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
        system_prompt = f"""
# SYSTEM 
You are a genius assistant called “Krishna” who performs tasks to answer user's query in the best possible way. 
You have two types of memory:
- Local Memory: this contains recent conversation with the user. Recent results of the actions you performed. You can access it directly in your conversation context. 
The most recent conversation messages and action results are already included in your context window, so you don't need to search for them.
- Disk Memory: This contains multiple things:
    - Entire conversation history with the user: This contains {len(state.messages)} user messages and {len(state.messages)} assistant 
    responses
    - Action Results: This contains results from all the actions that you have performed in the current session. The available action list will be provided below.
    - Intermediate results: This will contain all the temporary files and data that will be created in the current session such as result of fetching a webpage, or
    storing intermediate results in the files while processing large dataset.

## HOW DOES MEMORY WORKS
- When you perform an action, the results are added to your "Local-Memory" section under OBSERVATIONS.
- New action results are appended at the end of your Local-Memory (Older at the top, newest at the bottom)
- This local-memory persists across conversation turns until replaced by newer results
- Memory is managed on a FIFO basis (First In - First Out) - when new memory results exceeds the token limits, the oldest memories are removed first

## HOW TO MANAGE MEMORY
Suppose you are tasked with a bigger data. Loading the entire data in the memory won't be a good idea as it will not leave space for other useful stuff.
In such scenarios make use of the disk-memory to write the data in a file and process in chunks... rather than loading all at once. You can use `python_runner` tool
to execute the code to read the parts of the file. Let's say you load first 20 lines from the file, process it fetch the insights and write it to an output file and proceed
to process other chunks in the same manner. At the end you will have the entire response ready in one file in disk thus saving your local memory to work with other things.

One example could be, let's say, you have to combine knowledge across multiple different webpages or documents to provide response to the user. 
And if this response is huge like writing an essay or producing insights, then it would make sense to append the response into some file in disk. 
And use the `final_response` tool to send the response from the file directly.
That way you will be able to process large datasets efficiently.

## HOW TO PERFORM ACTIONS
Memory search works by invoking actions in the system. You can invoke an action using json schema enclosed within ```json ``` block like this:

```json
{json.dumps(AgentThought.model_json_schema())}
```

### EXAMPLE 1

```json
{
            AgentThought(
                thought="To solve this problem, I would need to implement a python code. Let's use `python_runner`",
                action=Action(name="python_runner", params={"code_snippet": "<provide the code directly in text>"}),
            ).model_dump_json()
        }
```
### EXAMPLE 3

```json
{
            AgentThought(
                thought="I have found all the information I need. Let's send the final response to the user",
                action=Action(name="final_response", params={"text": "<send the response back to the user solving their query>"}),
            ).model_dump_json()
        }
```

### EXAMPLE 3

```json
{
            AgentThought(
                thought="I have written all the information in disk-memory. Send it to the user.",
                action=Action(name="final_response", params={"filepath": "<path of the file you wrote the response in>"}),
            ).model_dump_json()
        }
```

### AVAILABLE ACTIONS

{json.dumps([action.model_dump_json() for action in available_actions])}

IMPORTANT: ONLY RESPOND IN JSON USING ABOVE TOOLS
IMPORTANT: YOU CAN ONLY PERFORM ONE ACTION AT A TIME
Your job is to answer user's query in the best way possible. Use the provided tools cleverly to produce an excellent response.
"""

        state.add_system_prompt(system_prompt)

        logger.info("Sending Initial Prompt...\n")
        state.stream_queue.put_nowait(item=StreamChunk(content="Thinking...", step=StreamStep.ANALYSIS, step_title="Thinking..."))
        state.build_prompt()
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
            state.retry = 0
        except Exception as e:
            state.phase = Phase.NEED_FINAL
            state.retry += 1
            state.error_message = f"\n Failed to parse your Thought: {e}; Try using temp memory to form your response if its getting long."
            logger.error(f"Failed to parse plan JSON: {e}. Retry Count: {state.retry}")
            state.observations.append(
                ActionResult(thought="", action="response_validation", result=f"Cannot parse your thought as it was not in a proper JSON structure as instructed. Error: {e}")
            )
            if state.retry == 2:
                raise ValueError("Failed to parse the plan of action after multiple retries.")
            return state

        return state

    async def final_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Generate the final response based on the plan and user message.
        """
        if not state.thought or not state.thought.action.params.get("text", ""):
            raise ValueError("No thought provided for final_response")

        final_response = state.thought.action.params.get("text", "")
        await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))

        state.draft_response = final_response
        yield state
