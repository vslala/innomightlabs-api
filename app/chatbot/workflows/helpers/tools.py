import asyncio
import io
import json
import os
import tempfile
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
import wikipedia

from app.chatbot.chatbot_models import Action, ActionResult, AgentState, StreamChunk
from app.common.models import StreamStep
from contextlib import redirect_stdout

_shared_ns: dict = {}

available_actions = [
    Action(name="list_tools", description="List all available tools.", params={}),
    Action(name="intermediate_response", description="Sends the intermediate response to the user from the params.", params={"text": "string"}),
    Action(name="final_response", description="Sends the final response to the user from the params.", params={"text": "string"}),
    Action(name="python_runner", description="Run a Python code snippet.", params={"code_snippet": "string"}),
    Action(name="wikipedia_search", description="Search Wikipedia and return a short summary.", params={"query": "string"}),
    Action(
        name="fetch_webpage",
        description="Fetches the webpage and saves it in local temporary memory and adds the path of the file to observations for later processing at will using python code",
        params={"url": "string"},
    ),
]


async def list_tools_tool(state: AgentState) -> ActionResult:
    if not state.thought or (state.thought and state.thought.action.name != "python_runner"):
        return ActionResult(thought="", action="None", result="")

    tools = [
        Action(name="python_runner", description="Run a Python code snippet.", params={"code_snippet": "string"}),
        Action(name="wikipedia_search", description="Search Wikipedia and return a short summary.", params={"query": "string"}),
        Action(name="final_response", description="Sends the final response to the user from the params.", params={"text": "string"}),
        Action(
            name="fetch_webpage",
            description="Fetches the webpage and saves it in local temporary memory and adds the path of the file to observations for later processing at will using python code",
            params={"url": "string"},
        ),
    ]

    return ActionResult(thought=state.thought.thought, action="list_tools", result=json.dumps([str(tool) for tool in tools], indent=2))


async def download_webpage_by_url(state: AgentState) -> ActionResult:
    """
    Tool: fetch the URL in state.thought.params["url"], scrape out the text,
    and saves it in the temp file
    Returns the path of the file as observation
    """
    if not state.thought or (state.thought and state.thought.action.name != "fetch_webpage"):
        return ActionResult(thought="", action="None", result="")

    url = state.thought.action.params["url"]
    # 1) fetch HTML
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as resp:
            await state.stream_queue.put(StreamChunk(content=f"Fetching {url}...", step=StreamStep.ANALYSIS, step_title="Fetching Webpage"))
            html = await resp.text()

    # 2) extract plain text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # 2) Create a temp file in the system temp directory
    #    delete=False so it sticks around after closing
    fd, path = tempfile.mkstemp(suffix=".html", prefix="page_", dir=None)
    os.close(fd) 

    # 3) Write the HTML
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return ActionResult(thought=state.thought.thought, action=state.thought.action.name, result=json.dumps({"url": url, "filepath": path}))


async def python_code_runner_tool(state: AgentState) -> ActionResult:
    """
    Execute the provided Python code snippet.
    :param action: The action containing the code snippet to run.
    :return: The result of the executed code.
    """

    buf = io.StringIO()

    def _run():
        with redirect_stdout(buf):
            exec(code_snippet, _shared_ns, _shared_ns)
        return buf.getvalue(), _shared_ns

    logger.info("\n\nExecuting python_runner...")
    if not state.thought or (state.thought and state.thought.action.name != "python_runner"):
        return ActionResult(thought="", action="None", result="")

    latest_thought = state.thought
    action = latest_thought.action
    code_snippet = action.params.get("code_snippet", "")
    if not code_snippet:
        raise ValueError("No code snippet provided to run.")

    state.stream_queue.put_nowait(StreamChunk(content=f"{latest_thought.thought}", step=StreamStep.ANALYSIS, step_title="Running Python Code"))
    logger.info(f"\n\nRunning code...\n{code_snippet}\n\n")
    result = None
    try:
        # Offload to a thread so we don’t block the loop
        out, result_vars = await asyncio.to_thread(_run)
        # 3) Merge captured stdout into your result payload
        payload = {"stdout": out}
        result = ActionResult(thought=latest_thought.thought, action="python_runner", result=str(payload))
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        result = ActionResult(thought=latest_thought.thought, action="python_runner", result=str(e))

    logger.info(f"\nGot the result: {result}\n\n")
    return result


async def wikipedia_search_tool(state: AgentState) -> ActionResult:
    """
    Perform a Wikipedia search for the given query.
    Expects the most recent thought with tool == "wikipedia_search"
    and params["query"] set to the search term.
    """
    # Find the last wikipedia_search action
    if not state.thought or (state.thought and state.thought.action.name != "wikipedia_search"):
        return ActionResult(thought="", action="None", result="")

    action = state.thought.action
    query = action.params.get("query", "").strip()
    if not query:
        return ActionResult(thought="", action="None", result="No query provided for wikipedia_search.")

    # Notify user we’re searching
    state.stream_queue.put_nowait(StreamChunk(content=f"🔍 Searching Wikipedia for “{query}”", step=StreamStep.ANALYSIS, step_title="Wikipedia Search"))

    try:
        # Do the search and grab the summary
        page = wikipedia.page(query, auto_suggest=False)
        summary = wikipedia.summary(query, sentences=2, auto_suggest=False)
        result = ActionResult(thought=state.thought.thought, action="wikipedia_search", result=f"**{page.title}**\n\n{summary}".strip())
    except Exception as e:
        result = ActionResult(thought=state.thought.thought, action="wikipedia_search", result=f"Wikipedia search failed: {e}")

    # Return the result so router can append to state.observations
    return result


async def final_response_tool(state: AgentState) -> ActionResult:
    """
    Generate the final response based on the plan and user message.
    """
    if not state.thought or (state.thought and state.thought.action.name != "python_runner"):
        return ActionResult(thought="", action="None", result="")

    final_response = state.thought.action.params.get("text", "")
    await state.stream_queue.put(StreamChunk(content="Finalizing Response...", step=StreamStep.DRAFT, step_title=""))
    await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))

    return ActionResult(thought=state.thought.thought, action="final_response", result=final_response)


async def intermediate_response_tool(state: AgentState) -> ActionResult:
    """
    Generate the final response based on the plan and user message.
    """
    if not state.thought or (state.thought and state.thought.action.name != "intermediate_response"):
        return ActionResult(thought="", action="None", result="")

    response = state.thought.action.params.get("text", "")
    await state.stream_queue.put(StreamChunk(content=response, step=StreamStep.REASONING, step_title="Thoughts"))

    return ActionResult(thought=state.thought.thought, action="intermediate_response", result=response)


tools = {
    "python_runner": python_code_runner_tool,
    "wikipedia_search": wikipedia_search_tool,
    "list_tools": list_tools_tool,
    "intermediate_response": intermediate_response_tool,
    "final_response": final_response_tool,
    "fetch_webpage": download_webpage_by_url,
}
