import asyncio
import io
import json
from loguru import logger
import wikipedia

from app.chatbot.chatbot_models import Action, ActionResult, AgentState, StreamChunk
from app.common.models import StreamStep
from contextlib import redirect_stdout


available_actions = [
    Action(name="list_tools", description="List all available tools.", params={}),
    Action(name="intermediate_response", description="Sends the intermediate response to the user from the params.", params={"text": "string"}),
    Action(name="final_response", description="Sends the final response to the user from the params.", params={"text": "string"}),
    Action(name="python_runner", description="Run a Python code snippet.", params={"code_snippet": "string"}),
    Action(name="wikipedia_search", description="Search Wikipedia and return a short summary.", params={"query": "string"}),
]


async def list_tools_tool(state: AgentState) -> ActionResult:
    thoughts = list(filter(lambda thought: thought.action.name == "list_tools", state.thoughts))
    if len(thoughts) == 0:
        return ActionResult(thought="", action="None", result="")

    tools = [
        Action(name="python_runner", description="Run a Python code snippet.", params={"code_snippet": "string"}),
        Action(name="wikipedia_search", description="Search Wikipedia and return a short summary.", params={"query": "string"}),
        Action(name="final_response", description="Sends the final response to the user from the params.", params={"text": "string"}),
    ]

    return ActionResult(thought=thoughts[0].thought, action="list_tools", result=json.dumps([str(tool) for tool in tools], indent=2))


async def python_code_runner_tool(state: AgentState) -> ActionResult:
    """
    Execute the provided Python code snippet.
    :param action: The action containing the code snippet to run.
    :return: The result of the executed code.
    """

    buf = io.StringIO()

    def _run():
        with redirect_stdout(buf):
            local_vars = {}
            exec(code_snippet, {}, local_vars)
        return buf.getvalue(), local_vars

    logger.info("\n\nExecuting python_runner...")
    thoughts = list(filter(lambda thought: thought.action.name == "python_runner", state.thoughts))
    if len(thoughts) == 0:
        return ActionResult(thought="", action="None", result="")

    action = thoughts[0].action
    code_snippet = action.params.get("code_snippet", "")
    if not code_snippet:
        raise ValueError("No code snippet provided to run.")

    state.stream_queue.put_nowait(StreamChunk(content=f"{thoughts[0].thought}", step=StreamStep.ANALYSIS, step_title="Running Python Code"))
    logger.info(f"\n\nRunning code...\n{code_snippet}\n\n")
    result = None
    try:
        # Offload to a thread so we don’t block the loop
        out, result_vars = await asyncio.to_thread(_run)
        # 3) Merge captured stdout into your result payload
        payload = {"stdout": out, "locals": result_vars}
        result = ActionResult(thought=thoughts[0].thought, action="python_runner", result=str(payload))
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        result = ActionResult(thought=thoughts[0].thought, action="python_runner", result=str(e))

    logger.info(f"\nGot the result: {result}\n\n")
    return result


async def wikipedia_search_tool(state: AgentState) -> ActionResult:
    """
    Perform a Wikipedia search for the given query.
    Expects the most recent thought with tool == "wikipedia_search"
    and params["query"] set to the search term.
    """
    # Find the last wikipedia_search action
    thoughts = [t for t in state.thoughts if t.action.name == "wikipedia_search"]
    if not thoughts:
        return ActionResult(thought="", action="None", result="")

    action = thoughts[-1].action
    query = action.params.get("query", "").strip()
    if not query:
        return ActionResult(thought="", action="None", result="No query provided for wikipedia_search.")

    # Notify user we’re searching
    state.stream_queue.put_nowait(StreamChunk(content=f"🔍 Searching Wikipedia for “{query}”", step=StreamStep.ANALYSIS, step_title="Wikipedia Search"))

    try:
        # Do the search and grab the summary
        page = wikipedia.page(query, auto_suggest=False)
        summary = wikipedia.summary(query, sentences=2, auto_suggest=False)
        result = ActionResult(thought=thoughts[0].thought, action="wikipedia_search", result=f"**{page.title}**\n\n{summary}".strip())
    except Exception as e:
        result = ActionResult(thought=thoughts[0].thought, action="wikipedia_search", result=f"Wikipedia search failed: {e}")

    # Return the result so router can append to state.observations
    return result


async def final_response_tool(state: AgentState) -> ActionResult:
    """
    Generate the final response based on the plan and user message.
    """
    thoughts = list(filter(lambda thought: thought.action.name == "final_response", state.thoughts))
    final_response = thoughts[0].action.params.get("text", "") if thoughts else ""
    await state.stream_queue.put(StreamChunk(content="Finalizing Response...", step=StreamStep.DRAFT, step_title=""))
    await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))

    return ActionResult(thought=thoughts[0].thought, action="final_response", result=final_response)


async def intermediate_response_tool(state: AgentState) -> ActionResult:
    """
    Generate the final response based on the plan and user message.
    """
    thoughts = list(filter(lambda thought: thought.action.name == "intermediate_response", state.thoughts))
    response = thoughts[0].action.params.get("text", "") if thoughts else ""
    await state.stream_queue.put(StreamChunk(content=response, step=StreamStep.REASONING, step_title="Thoughts"))

    return ActionResult(thought=thoughts[0].thought, action="intermediate_response", result=response)


tools = {
    "python_runner": python_code_runner_tool,
    "wikipedia_search": wikipedia_search_tool,
    "list_tools": list_tools_tool,
    "intermediate_response": intermediate_response_tool,
    "final_response": final_response_tool,
}
