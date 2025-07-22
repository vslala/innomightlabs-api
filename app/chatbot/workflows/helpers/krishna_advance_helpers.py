import asyncio
from collections.abc import AsyncGenerator
import json
from loguru import logger
import re

import wikipedia

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState, AgentThought, StreamChunk
from app.common.models import StreamStep


JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def extract_json_block(text: str) -> str:
    """
    Extracts the first JSON array block wrapped in triple backticks.
    """
    match = JSON_BLOCK_RE.findall(text)
    return match[0] if match else text.strip("` \n")


def route_condition(state: AgentState) -> str:
    """
    Determine if the final response action is present in the thoughts.
    """
    final_response = any(thought.action.tool == "final_response" for thought in state.thoughts)
    if final_response:
        return "final_response"
    return "continue"


async def python_code_runner_tool(state: AgentState) -> str:
    """
    Execute the provided Python code snippet.
    :param action: The action containing the code snippet to run.
    :return: The result of the executed code.
    """
    thoughts = list(filter(lambda thought: thought.action.tool == "python_runner", state.thoughts))
    if len(thoughts) == 0:
        return ""

    action = thoughts[0].action
    code_snippet = action.params.get("code_snippet", "")
    if not code_snippet:
        raise ValueError("No code snippet provided to run.")

    await state.stream_queue.put(StreamChunk(content=f"{thoughts[0].thought}", step=StreamStep.ANALYSIS, step_title="Running Python Code"))

    try:
        # Execute the code snippet and capture the output
        local_vars = {}
        exec(code_snippet, {}, local_vars)

        return f"""
            [Thought]
            {thoughts[0].thought}
            [Tool Used] 
            python_runner
            [Tool Result]
            {str(local_vars)}
        """.strip()
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return f"""
            [Thought]
            {thoughts[0].thought}
            [Tool Used] 
            python_runner
            [Tool Result]
            {str(e)}
        """


async def wikipedia_search_tool(state: AgentState) -> str:
    """
    Perform a Wikipedia search for the given query.
    Expects the most recent thought with tool == "wikipedia_search"
    and params["query"] set to the search term.
    """
    # Find the last wikipedia_search action
    thoughts = [t for t in state.thoughts if t.action.tool == "wikipedia_search"]
    if not thoughts:
        return ""

    action = thoughts[-1].action
    query = action.params.get("query", "").strip()
    if not query:
        return "No query provided for wikipedia_search."

    # Notify user we’re searching
    await state.stream_queue.put(StreamChunk(content=f"🔍 Searching Wikipedia for “{query}”", step=StreamStep.ANALYSIS, step_title="Wikipedia Search"))

    try:
        # Do the search and grab the summary
        page = wikipedia.page(query, auto_suggest=False)
        summary = wikipedia.summary(query, sentences=2, auto_suggest=False)
        result = f"""
            [Thought]
            {thoughts[0].thought}
            [Tool Used] 
            wikipedia_search
            [Tool Result]
            **{page.title}**\n\n{summary}
        """.strip()
    except Exception as e:
        result = f"""
            [Thought]
            {thoughts[0].thought}
            [Tool Used] 
            wikipedia_search
            [Tool Result]
            Wikipedia search failed: {e}
        """.strip()

    # Return the result so router can append to state.observations
    return result


class KrishnaAdvanceWorkflowHelper:
    def __init__(self, chatbot: BaseChatbot) -> None:
        self.chatbot = chatbot

    async def router(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Execute the actions in the plan.
        This method processes each action in the plan and executes it.
        """
        logger.info("Running provided actions...")
        await state.stream_queue.put(StreamChunk(content="Executing planned actions…", step=StreamStep.ANALYSIS, step_title="Executing Actions"))

        tools = {
            "python_runner": python_code_runner_tool,
            "wikipedia_search": wikipedia_search_tool,
        }

        tasks = []
        for tool in tools.values():
            task = asyncio.create_task(tool(state=state))
            tasks.append(task)
        observations = await asyncio.gather(*tasks, return_exceptions=False)

        logger.info(f"Got the observations: {observations}")
        state.observations.extend(observations)

        yield state

    async def thinker(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        analysis_prompt = f"""
            Analyze the following user query and conversation context:

            [Conversation History]
            {state.build_conversation_history()}

            [Current Query]
            \"\"\"{state.user_message}\"\"\"
            
            {"[Observations]\n" + "\n".join(state.observations) if state.observations else ""}

            Understand the user's intent based on the current query, previous messages and observations.
            If you need to perform any further actions, create a plan of action that includes your thoughts and the actions you want to perform.
            Once you pass the plan, the actions will be executed and result will be sent back to you under [Observations] for further analysis.
            
            IMPORTANT: The plan should include your thoughts and the action you want to perform wrapped within ```json ```. For example:

            ```json
            [
                {{
                    "thought": "I need to fetch past conversations to understand the user's context better.",
                    "action": {{
                        "tool": "search_past_conversations",
                        "params": {{
                            "query": "messages regarding black hole discussion on how black holes are formed",
                            "limit": 5
                        }}
                    }}
                }},
            ]
            ```
            ## Available tools:

            [
                {{
                    "tool": "python_runner",
                    "description": "Run a Python code snippet.",
                    "params": {{
                        "code_snippet": "string"
                    }}
                }},
                {{
                    "tool": "wikipedia_search",
                    "description": "Search Wikipedia and return a short summary.",
                    "params": {{
                        "query": "string"
                    }}
                }},
                {{
                    "tool": "final_response",
                    "description": "Sends the final response to the user from the params.",
                    "params": {{
                        "text": "string"
                    }}
                }}
            ]

            Remember, you will get back the observation of the action you performed 
            and then you can choose to send the final response to the user with `final_response` tool. 
            You can only communicate using the provided tools and their parameters. Do not communicate in any other way.
            """

        plan_of_action = ""
        async for chunk in self.chatbot.stream_response(prompt=analysis_prompt):
            plan_of_action += str(chunk)
            await state.stream_queue.put(StreamChunk(content=str(chunk), step=StreamStep.ANALYSIS, step_title="Analysing User Query"))

        parsed_json = extract_json_block(plan_of_action.strip()[7:-3])
        try:
            json_text = extract_json_block(parsed_json)
            state.thoughts = [AgentThought(**item) for item in json.loads(json_text)]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}. Falling back to raw parse.")
            raise ValueError("Failed to parse the plan of action. Please ensure the response is in the correct JSON format.")
        finally:
            yield state

    async def final_response(self, state: AgentState) -> AsyncGenerator[AgentState, None]:
        """
        Generate the final response based on the plan and user message.
        """
        thoughts = list(filter(lambda thought: thought.action.tool == "final_response", state.thoughts))
        final_response = thoughts[0].action.params.get("text", "") if thoughts else ""

        await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))
        yield state
