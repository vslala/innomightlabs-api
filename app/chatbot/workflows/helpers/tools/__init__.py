import asyncio
import io
import json
import os
import tempfile
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel
import wikipedia
from contextlib import redirect_stdout
from pdfminer.high_level import extract_text
from langchain.tools import tool, BaseTool

from app.chatbot.chatbot_models import ActionResult, AgentState, StreamChunk
from app.chatbot.workflows.helpers.tools.memory_tools import BaseParamsModel, memory_tools_v2
from app.chatbot.workflows.helpers.tools import text_editor_tools, browser_tools
from app.common.models import StreamStep

_shared_ns: dict = {}
_message_repository = None
_memory_manager = None
_embedder = None


def get_memory_manager():
    global _memory_manager
    if _memory_manager is None:
        from app.common.config import RepositoryFactory

        _memory_manager = RepositoryFactory.get_memory_manager_repository()
    return _memory_manager


def get_embedder():
    global _embedder
    if _embedder is None:
        from app.common.config import ChatbotFactory

        _embedder = ChatbotFactory.get_embedding_model("titan")
    return _embedder


def get_message_repository():
    global _message_repository
    if _message_repository is None:
        from app.common.config import RepositoryFactory

        _message_repository = RepositoryFactory.get_message_repository()
    return _message_repository


class SendMessageParams(BaseModel):
    """Sends the message to the user"""

    message: str


@tool(
    "send_message",
    description="Sends the message to the user. Always provide markdown text so it can be rendered properly for the user.",
    args_schema=SendMessageParams,
    infer_schema=False,
    return_direct=True,
)
async def send_message(state: AgentState, input: SendMessageParams) -> ActionResult:
    state.stream_queue.put_nowait(StreamChunk(content=input.message, step=StreamStep.FINAL_RESPONSE, step_title="Sending message to user"))
    return ActionResult(thought="", action="send_message", result="Message sent successfully!")


class PythonCodeRunnerParams(BaseParamsModel):
    """Runs python code and returns the output"""

    thought: str
    code: str


@tool(
    "python_code_runner",
    description="Executes python code and adds the result to working context",
    args_schema=PythonCodeRunnerParams,
    infer_schema=True,
    return_direct=True,
)
async def python_code_runner(state: AgentState, input: PythonCodeRunnerParams) -> ActionResult:
    """
    Execute the provided Python code snippet.
    :param action: The action containing the code snippet to run.
    :return: The result of the executed code.
    """

    def _run():
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(input.code, _shared_ns, _shared_ns)
        return buf.getvalue(), _shared_ns

    logger.info("\n\nExecuting python_runner...")

    state.stream_queue.put_nowait(StreamChunk(content=input.thought, step=StreamStep.ANALYSIS, step_title="Running Python Code"))
    logger.info(f"\n\nRunning code...\n{input.code}\n\n")
    result = None
    try:
        task = asyncio.to_thread(_run)
        out, result_vars = await asyncio.wait_for(task, timeout=30)
        result = ActionResult(thought=input.thought, action="python_code_runner", result=f"Code:\n{input.code}\nCode executed. Output: {out or '(no output)'}")
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        result = ActionResult(thought=input.thought, action="python_code_runner", result=f"Code execution failed: {str(e)}")

    logger.info(f"\nGot the result: {result}\n\n")
    return result


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


class DownloadWebPageByUrlParams(BaseModel):
    url: str


@tool(
    "download_webpage_by_url",
    description="Downloads the webpage to local temp from the given url and provides the file path. You can use file reading tools to read the data.",
    args_schema=DownloadWebPageByUrlParams,
    infer_schema=False,
    return_direct=True,
)
async def download_webpage_by_url(state: AgentState, input: DownloadWebPageByUrlParams) -> ActionResult:
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
                    result=f"Your downloaded webpage ({url}) can be read from following path: {txt_path}",
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
                    result=f"Your downloaded webpage ({url}) can be read from following path: {html_path}",
                )


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
    return result


memory_actions: list[BaseTool] = memory_tools_v2
additional_actions: list[BaseTool] = [send_message, python_code_runner, text_editor_tools.text_editor, browser_tools.download_webpage]
available_actions = memory_actions + additional_actions


new_tools = {}
for my_tool in available_actions:
    new_tools[my_tool.name] = my_tool
