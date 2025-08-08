import asyncio
from collections import deque
from datetime import datetime, timezone
import io
import json
import os
import tempfile
from uuid import UUID, uuid4
import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel, Field
import wikipedia

from app.chatbot.chatbot_models import ActionResult, AgentState, MemoryEntry, MemoryType, StreamChunk
from app.chatbot.workflows.memories.memory_tools import BaseParamsModel, memory_tools_v2
from app.common.models import StreamStep
from contextlib import redirect_stdout
from pdfminer.high_level import extract_text
from langchain.tools import tool, BaseTool

_shared_ns: dict = {}

# MEMORY TOOLS - Initialize lazily to avoid circular imports
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


def _manage_memory_overflow(state: AgentState, memory_type_enum: MemoryType, new_entry_size: int) -> None:
    """Check for memory overflow and evict entries to maintain 50% capacity"""
    from app.common.models import MemoryManagementConfig

    # Get the appropriate memory deque based on memory type
    if memory_type_enum in [MemoryType.ARCHIVAL, MemoryType.SUMMARY, MemoryType.USER_PROFILE, MemoryType.PERSONA]:
        memory_deque = state.archival_memory
    elif memory_type_enum == MemoryType.RECALL:
        memory_deque = state.recall_memory
    else:
        return

    # Calculate current usage in characters (similar to get_memory_overflow_alert)
    current_chars = sum(len(entry.content) for entry in memory_deque)

    # Convert to tokens and check against memory type's token limit
    current_tokens = current_chars / MemoryManagementConfig.AVERAGE_TOKEN_SIZE
    new_entry_tokens = new_entry_size / MemoryManagementConfig.AVERAGE_TOKEN_SIZE
    total_tokens_after_add = current_tokens + new_entry_tokens

    # Check if would exceed 100% capacity (vs 80% threshold used in alerts)
    if total_tokens_after_add > memory_type_enum.token_limit:
        target_tokens = memory_type_enum.token_limit * 0.5  # 50% capacity
        target_chars = int(target_tokens * MemoryManagementConfig.AVERAGE_TOKEN_SIZE)
        evicted_ids = []

        # Evict from front (FIFO) until we reach target
        while memory_deque and current_chars > target_chars:
            evicted_entry = memory_deque.popleft()
            current_chars -= len(evicted_entry.content)
            evicted_ids.append(evicted_entry.id)

        # Evict from persistent storage
        if evicted_ids:
            get_memory_manager().evict_memory_batch(ids=evicted_ids)
            logger.info(f"Evicted {len(evicted_ids)} {memory_type_enum.value} memory entries to prevent overflow")


class ArchivalMemorySearchParams(BaseModel):
    thought: str
    query: str


@tool(
    "archival_memory_search",
    description="Retrieve information from your extensive archival memory into your working context.",
    args_schema=ArchivalMemorySearchParams,
    infer_schema=False,
    return_direct=True,
)
async def archival_memory_search(state: AgentState, input: ArchivalMemorySearchParams) -> ActionResult:
    embeddings = get_embedder().embed_single_text(input.query)
    results = get_memory_manager().search(user_id=state.user.id, embeddings=embeddings)

    # Check for overflow before adding results
    if results:
        new_content_size = sum(len(entry.content) for entry in results)
        _manage_memory_overflow(state, MemoryType.ARCHIVAL, new_content_size)
    else:
        return ActionResult(
            thought=input.thought, action="archival_memory_search", result="No results found in archival memory. Try using `conversation_search` to look into past conversations."
        )
    state.archival_memory.extend(results)
    return ActionResult(thought=input.thought, action="archival_memory_search", result=f"Found {len(results)} results. Added to archival memory.")


class ArchivalMemoryInsertParams(BaseModel):
    """Add new data to your archival memory, expanding your knowledge base."""

    data: str
    label: str
    metadata: dict[str, str] = Field(default={})


@tool(
    "archival_memory_insert",
    description="Add new data to your archival memory, expanding your knowledge base.",
    args_schema=ArchivalMemoryInsertParams,
    infer_schema=False,
    return_direct=True,
)
async def archival_memory_insert(state: AgentState, input: ArchivalMemoryInsertParams) -> ActionResult:
    memory_type = MemoryType(input.label.lower())

    # Check for overflow before adding new entry
    _manage_memory_overflow(state, memory_type, len(input.data))

    entry = MemoryEntry(
        id=uuid4(), user_id=state.user.id, memory_type=memory_type, content=input.data, embedding=get_embedder().embed_single_text(input.data), metadata=input.metadata
    )

    get_memory_manager().update_memory(entry)
    state.archival_memory.append(entry)
    return ActionResult(thought="Insert into archival memory", action="archival_memory_insert", result=f"Archival memory inserted with ID: {entry.id} and data: {entry.content}")


class ArchivalMemoryUpdateParams(BaseModel):
    """Updates existing archival memory, keeping your knowledge base up-to-date and accurate"""

    label: str
    memory_id: UUID
    data: str
    metadata: dict[str, str] = Field(default={})


@tool(
    "archival_memory_update",
    description="Updates existing archival memory, keeping your knowledge base up-to-date and accurate",
    args_schema=ArchivalMemoryUpdateParams,
    infer_schema=False,
    return_direct=True,
)
async def archival_memory_update(state: AgentState, input: ArchivalMemoryUpdateParams) -> ActionResult:
    entry = MemoryEntry(
        id=input.memory_id,
        user_id=state.user.id,
        memory_type=MemoryType(input.label.lower()),
        created_at=datetime.now(timezone.utc),
        content=input.data,
        embedding=get_embedder().embed_single_text(input.data),
        metadata=input.metadata,
    )

    get_memory_manager().update_memory(entry)
    for idx, item in enumerate(state.archival_memory):
        if item.id == entry.id:
            # replace the old with the new
            state.archival_memory[idx] = entry
            break

    return ActionResult(
        thought="Update archival memory block in place", action="archival_memory_update", result=f"Archival memory updated with ID: {entry.id} and content: {entry.content}"
    )


class ArchivalMemoryEvictParams(BaseModel):
    """Updates existing archival memory, keeping your knowledge base up-to-date and accurate"""

    memory_ids: list[UUID]


@tool(
    "archival_memory_evict",
    description="Removes list of memory by ID that is not required in order to free up space for later use",
    args_schema=ArchivalMemoryEvictParams,
    infer_schema=False,
    return_direct=True,
)
async def archival_memory_evict(state: AgentState, input: ArchivalMemoryEvictParams) -> ActionResult:
    get_memory_manager().evict_memory_batch(ids=input.memory_ids)
    state.archival_memory = deque([entry for entry in state.archival_memory if entry.id not in input.memory_ids])
    return ActionResult(
        thought="Remove memory blocks from working memory to free up space",
        action="archival_memory_evict",
        result=f"Archival memory with Ids: {input.memory_ids} evicted successfully",
    )


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


class ConversationSearchParams(BaseParamsModel):
    """Recalls memory based on the provided query"""

    query: str
    page: int = Field(default=1)


@tool(
    "conversation_search",
    description="""Loads older conversation into working context as "recall" memory blocks
        - Use `page` param to scroll through older conversation if you don't find something in the given page
        - Do not go past the last page
        - If it returns [], _you must not call `conversation_search` again for the same query_.  
        - Instead, you should fall back to another action (e.g. send a clarification request to the user).  
        """,
    args_schema=ConversationSearchParams,
    infer_schema=False,
    return_direct=True,
)
async def conversation_search(state: AgentState, input: ConversationSearchParams) -> ActionResult:
    """
    Recalls memory based on the provided query with pagination support.
    """
    from app.chatbot.chatbot_models import PaginatedMemoryResult

    embeddings = get_embedder().embed_single_text(input.query)
    paginated_result: PaginatedMemoryResult = await get_message_repository().search_paginated_by_user_id_and_embeddings(
        user_id=state.user.id, embeddings=embeddings, page=input.page
    )

    if not paginated_result.results:
        return ActionResult(thought="", action="conversation_search", result="[]")

    # Only add to state memory, don't persist to database
    state.recall_paginated_result = paginated_result

    result_msg = "Older conversation loaded into working context"

    return ActionResult(thought="", action="conversation_search", result=result_msg)


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


memory_actions: list[BaseTool] = memory_tools_v2 + [conversation_search]
additional_actions: list[BaseTool] = [send_message, python_code_runner]
available_actions = memory_actions + additional_actions


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


new_tools = {}
for my_tool in memory_actions:
    new_tools[my_tool.name] = my_tool
for my_tool in additional_actions:
    new_tools[my_tool.name] = my_tool
