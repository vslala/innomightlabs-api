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
from pdfminer.high_level import extract_text

_shared_ns: dict = {}

available_actions = [
    Action(name="list_tools", description="Lists more tools from the registry like fetch_webpage, write_data_to_temp_memory etc.", params={}),
    Action(name="python_runner", description="Run a Python code snippet.", params={"code_snippet": "string"}),
    Action(
        name="intermediate_response",
        description="If the response you are sending is too large you could use this tool to send it in multiple go. Sends the intermediate response to the user.",
        params={"text": "string"},
    ),
    Action(
        name="final_response",
        description="""
Sends the final response to the user in two ways:
- text: If text is provided then the response is directly sent from the text
- filepath: If filepath is provided (usually to send large response), then Krishna (you) can choose to write it in a disk-memory and then send the path to that file,
    and the content of that file will be sent to the user
""",
        params={"text?": "string", "filepath?": "string"},
    ),
    Action(name="wikipedia_search", description="Search Wikipedia and return a short summary.", params={"query": "string"}),
    Action(
        name="fetch_webpage",
        description="""
Fetches the webpage and write the data in the disk memory and adds the file path to the observatio/result. 
The file can be accessed by other tools or if you want to access parts of it you can use python code to do that.
""",
        params={"url": "string"},
    ),
    Action(
        name="write_data_to_disk_memory",
        description="""
Writes the data to a file on disk for later use. It works in the following ways:
data: actual data to write
filename_prefix (optional): use it to understand what the file content is about
    - You DO NOT need to provide filename_prefix if you are appending to the same file.
filepath (optional):
    - if filepath is provided then the content from `params.data` is appended to the same file.
    - if filepath is not provided then a new file will be created everytime.
""",
        params={"data": "string", "filename_prefix?": "string", "filepath?": "string"},
    ),
    Action(
        name="read_data_from_disk_memory",
        description="""
        Reads the data from a file on disk and adds it to local-memory action results
            filepath: reads the data from the provided filepath
        """,
        params={"filepath": "string"},
    ),
]


async def list_tools_tool(state: AgentState) -> ActionResult:
    if not state.thought or (state.thought and state.thought.action.name != "python_runner"):
        return ActionResult(thought="", action="None", result="")

    tools = available_actions[3:]

    return ActionResult(thought=state.thought.thought, action="list_tools", result=json.dumps([str(tool) for tool in tools], indent=2))


async def read_data_from_disk_memory(state: AgentState) -> ActionResult:
    if not state.thought or (state.thought and state.thought.action.name != "read_data_from_disk_memory"):
        return ActionResult(thought="", action="None", result="")

    state.stream_queue.put_nowait(StreamChunk(content=state.thought.thought, step=StreamStep.ANALYSIS, step_title="Reading into local memory"))

    filepath = state.thought.action.params.get("filepath")
    if not filepath:
        return ActionResult(thought=state.thought.thought, action=state.thought.action.name, result="Require filepath to load memory")
    with open(filepath, "r", encoding="utf-8") as f:
        data = f.read()
        return ActionResult(thought=state.thought.thought, action=state.thought.action.name, result=data)


async def write_data_to_disk_memory(state: AgentState) -> ActionResult:
    """
    Tool: writes the data to a temp file in the system temp directory so it can be retrieved later
    Params: {
        data: str,
        filename_prefix?: str,
        filepath?: str # full path to append to (optional)
    }
    Returns the path of the file as observation
    """
    if not state.thought or (state.thought and state.thought.action.name != "write_data_to_disk_memory"):
        return ActionResult(thought="", action="None", result="")

    state.stream_queue.put_nowait(StreamChunk(content=state.thought.thought, step=StreamStep.ANALYSIS, step_title="Writing to temp memory"))

    data = state.thought.action.params["data"]
    target = state.thought.action.params.get("filepath")

    if target:
        # append to (or create) the specified file
        path = target
        mode = "a"
    else:
        # make a brand‑new temp file
        prefix = state.thought.action.params.get("filename_prefix", "data_")
        fd, path = tempfile.mkstemp(suffix=".txt", prefix=prefix)
        os.close(fd)
        mode = "w"

    # write or append
    with open(path, mode, encoding="utf-8") as f:
        f.write(data)

    state.filepaths.append(path)
    return ActionResult(thought=state.thought.thought, action=state.thought.action.name, result=json.dumps({"filepath": path}))


# async def download_webpage_by_url(state: AgentState) -> ActionResult:
#     """
#     Tool: fetch the URL in state.thought.params["url"], scrape out the text,
#     and saves it in the temp file
#     Returns the path of the file as observation
#     """
#     if not state.thought or (state.thought and state.thought.action.name != "fetch_webpage"):
#         return ActionResult(thought="", action="None", result="")

#     state.stream_queue.put_nowait(StreamChunk(content=f"{state.thought.thought}", step=StreamStep.ANALYSIS, step_title="Fetching Webpage"))
#     url = state.thought.action.params["url"]
#     # 1) fetch HTML
#     async with aiohttp.ClientSession() as sess:
#         async with sess.get(url) as resp:
#             await state.stream_queue.put(StreamChunk(content=f"Fetching {url}...", step=StreamStep.ANALYSIS, step_title="Fetching Webpage"))
#             html = await resp.text()

#     # 2) extract plain text
#     soup = BeautifulSoup(html, "html.parser")
#     text = soup.get_text(separator=" ", strip=True)

#     # 2) Create a temp file in the system temp directory
#     #    delete=False so it sticks around after closing
#     fd, path = tempfile.mkstemp(suffix=".html", prefix="page_", dir=None)
#     os.close(fd)

#     # 3) Write the HTML
#     with open(path, "w", encoding="utf-8") as f:
#         f.write(text)
#     return ActionResult(thought=state.thought.thought, action=state.thought.action.name, result=json.dumps({"url": url, "filepath": path}))


async def download_webpage_by_url(state: AgentState) -> ActionResult:
    """
    Tool: fetch the URL in state.thought.params["url"], decide if it's HTML or PDF,
    extract plain text, save it in a temp file (and PDF in a temp file if needed),
    and return the filepath(s) in the result.
    """
    if not state.thought or state.thought.action.name != "fetch_webpage":
        return ActionResult(thought="", action="None", result="")

    url = state.thought.action.params["url"]
    await state.stream_queue.put(StreamChunk(content=f"Fetching {url}…", step=StreamStep.ANALYSIS, step_title="Fetching Webpage"))

    async with aiohttp.ClientSession() as sess:
        async with sess.get(url) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            is_pdf = "application/pdf" in content_type or url.lower().endswith(".pdf")

            if is_pdf:
                # 1) Download PDF bytes
                pdf_bytes = await resp.read()

                # 2) Write to a temp PDF file
                pdf_fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="page_", dir=None)
                os.close(pdf_fd)
                with open(pdf_path, "wb") as f_pdf:
                    f_pdf.write(pdf_bytes)
                await state.stream_queue.put(StreamChunk(content="Saved PDF to temp file, extracting text…", step=StreamStep.SYNTHESIS, step_title=StreamStep.SYNTHESIS.value))

                # 3) Extract text with pdfminer
                text = extract_text(pdf_path)

                # 4) Write extracted text to a temp .txt file
                txt_fd, txt_path = tempfile.mkstemp(suffix=".txt", prefix="page_", dir=None)
                os.close(txt_fd)
                with open(txt_path, "w", encoding="utf-8") as f_txt:
                    f_txt.write(text)

                await state.stream_queue.put(StreamChunk(content="Extraction complete.", step=StreamStep.ANALYSIS, step_title=StreamStep.SYNTHESIS.value))
                output_paths = {
                    "url": url,
                    "pdf_filepath": pdf_path,
                    "text_filepath": txt_path,
                }
                state.filepaths.append(json.dumps(output_paths, indent=2))
                return ActionResult(
                    thought=state.thought.thought,
                    action=state.thought.action.name,
                    result=json.dumps(output_paths),
                )

            else:
                # HTML path (unchanged)
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator=" ", strip=True)

                html_fd, html_path = tempfile.mkstemp(suffix=".html", prefix="page_", dir=None)
                os.close(html_fd)
                with open(html_path, "w", encoding="utf-8") as f_html:
                    f_html.write(text)

                state.filepaths.append(
                    json.dumps(
                        {
                            "url": url,
                            "filepath": html_path,
                        },
                        indent=2,
                    )
                )
                return ActionResult(
                    thought=state.thought.thought,
                    action=state.thought.action.name,
                    result=json.dumps(
                        {
                            "url": url,
                            "filepath": html_path,
                        }
                    ),
                )


async def python_code_runner_tool(state: AgentState) -> ActionResult:
    """
    Execute the provided Python code snippet.
    :param action: The action containing the code snippet to run.
    :return: The result of the executed code.
    """

    def _run():
        buf = io.StringIO()
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
        task = asyncio.to_thread(_run)
        out, result_vars = await asyncio.wait_for(task, timeout=30)
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
    Params:
        text?: sends the provided text to the user as final response
        filepath?: fetches the contents from the filepath and sends it to the user as final response
    """
    if not state.thought or (state.thought and state.thought.action.name != "python_runner"):
        return ActionResult(thought="", action="None", result="")

    final_response = state.thought.action.params.get("text")
    if final_response:
        await state.stream_queue.put(StreamChunk(content="Finalizing Response...", step=StreamStep.DRAFT, step_title=""))
        await state.stream_queue.put(StreamChunk(content=final_response, step=StreamStep.FINAL_RESPONSE, step_title="Finalizing Response"))
        return ActionResult(thought=state.thought.thought, action="final_response", result=final_response)
    else:
        file_path = state.thought.action.params.get("filepath")
        if not file_path:
            return ActionResult(thought=state.thought.thought, action="final_response", result="Need atleast one param (text | filepath)")
        with open(file_path, "r") as f:
            for line in f:
                await state.stream_queue.put(StreamChunk(content=line, step=StreamStep.FINAL_RESPONSE, step_title="Sending response..."))
                await asyncio.sleep(0.1)
            return ActionResult(thought=state.thought.thought, action="final_response", result=f.read())


async def intermediate_response_tool(state: AgentState) -> ActionResult:
    """
    Generate the final response based on the plan and user message.
    """
    if not state.thought or (state.thought and state.thought.action.name != "intermediate_response"):
        return ActionResult(thought="", action="None", result="")

    response = state.thought.action.params.get("text", "")
    await state.stream_queue.put(StreamChunk(content=response, step=StreamStep.FINAL_RESPONSE, step_title="Thoughts"))

    return ActionResult(thought=state.thought.thought, action="intermediate_response", result=response)


tools = {
    "python_runner": python_code_runner_tool,
    "wikipedia_search": wikipedia_search_tool,
    "list_tools": list_tools_tool,
    "intermediate_response": intermediate_response_tool,
    "final_response": final_response_tool,
    "fetch_webpage": download_webpage_by_url,
    "write_data_to_disk_memory": write_data_to_disk_memory,
    "read_data_from_disk_memory": read_data_from_disk_memory,
}
