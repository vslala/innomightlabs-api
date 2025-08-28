from pydantic import BaseModel, Field
from app.common.utils import tool, SimpleTool as BaseTool

from app.chatbot.chatbot_models import ActionResult, AgentState, MemoryEntry
from app.common.models import MemoryType

# Initialize lazily to avoid circular imports
_memory_manager_v3 = None
_embedder = None


def get_memory_manager_v3():
    global _memory_manager_v3
    if _memory_manager_v3 is None:
        from app.common.config import RepositoryFactory

        _memory_manager_v3 = RepositoryFactory.get_memory_manager_v3_repository()
    return _memory_manager_v3


def get_embedder():
    global _embedder
    if _embedder is None:
        from app.common.config import ChatbotFactory

        _embedder = ChatbotFactory.get_embedding_model("titan")
    return _embedder


class MemoryAppendParams(BaseModel):
    memory_type: str
    content: str


@tool(
    "memory_append",
    description="Append text to a memory block. Creates new pages automatically when current page exceeds 100 tokens.",
    args_schema=MemoryAppendParams,
    return_direct=True,
)
async def memory_append(state: AgentState, input: MemoryAppendParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())
    embedding = get_embedder().embed_single_text(input.content)

    memory_entry = MemoryEntry(user_id=state.user.id, memory_type=memory_type, content=input.content, embedding=embedding, metadata={})

    result = get_memory_manager_v3().append(memory_entry)

    return ActionResult(
        thought="Appended to memory block",
        action="memory_append",
        result=f"Appended to {memory_type.value} block. Page {result.page}/{result.total_pages}, tokens: {result.total_count}",
    )


class MemoryReplaceParams(BaseModel):
    memory_type: str
    page: int
    old_text: str
    new_text: str


@tool(
    "memory_replace",
    description="Replace specific text within a memory page. Specify the page number to target.",
    args_schema=MemoryReplaceParams,
    return_direct=True,
)
async def memory_replace(state: AgentState, input: MemoryReplaceParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    try:
        result = get_memory_manager_v3().replace(user_id=state.user.id, memory_type=memory_type, page=input.page, old_txt=input.old_text, new_txt=input.new_text)

        return ActionResult(
            thought="Replaced text in memory page",
            action="memory_replace",
            result=f"Replaced '{input.old_text}' with '{input.new_text}' in {memory_type.value} page {result.page}/{result.total_pages}",
        )
    except ValueError as e:
        return ActionResult(thought="Memory page not found", action="memory_replace", result=str(e))


class MemoryEvictParams(BaseModel):
    memory_type: str
    page: int
    text: str


@tool(
    "memory_evict",
    description="Remove specific text from a memory page. Specify the page number to target.",
    args_schema=MemoryEvictParams,
    return_direct=True,
)
async def memory_evict(state: AgentState, input: MemoryEvictParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    try:
        result = get_memory_manager_v3().evict(user_id=state.user.id, memory_type=memory_type, page=input.page, text=input.text)

        return ActionResult(
            thought="Evicted text from memory page",
            action="memory_evict",
            result=f"Removed '{input.text}' from {memory_type.value} page {result.page}/{result.total_pages}, tokens: {result.total_count}",
        )
    except ValueError as e:
        return ActionResult(thought="Memory page not found", action="memory_evict", result=str(e))
    except Exception as e:
        return ActionResult(thought="Error evicting text from memory page", action="memory_evict", result=str(e))


class MemoryReadParams(BaseModel):
    memory_type: str
    query: str
    page: int = Field(default=1)


@tool(
    "memory_read",
    description="Search and read memory pages by semantic similarity. Returns the most relevant page for the query.",
    args_schema=MemoryReadParams,
    return_direct=True,
)
async def memory_read(state: AgentState, input: MemoryReadParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    try:
        result = get_memory_manager_v3().read(user_id=state.user.id, memory_type=memory_type, query=input.query, page=input.page)

        if not result.results:
            return ActionResult(thought="No memory found", action="memory_read", result=f"No memory blocks found for type '{memory_type.value}'")

        for entry in result.results:
            if entry.memory_type in state.memory_blocks:
                state.memory_blocks[entry.memory_type.value].append("\n" + entry.content)
            else:
                state.memory_blocks[entry.memory_type.value] = entry

        return ActionResult(
            thought="Retrieved memory page",
            action="memory_read",
            result=f"Memory '{memory_type.value}' page {result.page}/{result.total_pages} loaded into the working context.",
        )
    except ValueError as e:
        return ActionResult(thought="Memory page not found", action="memory_read", result=str(e))


# Export memory tools for LLM
memory_tools_v3: list[BaseTool] = [
    memory_append,
    memory_replace,
    memory_evict,
    memory_read,
]
