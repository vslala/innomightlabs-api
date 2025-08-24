from pydantic import BaseModel, Field
from app.common.utils import tool, SimpleTool as BaseTool

from app.chatbot.chatbot_models import ActionResult, AgentState
from app.common.models import MemoryType

# Initialize lazily to avoid circular imports
_memory_manager_v2 = None
_message_repository = None
_embedder = None


def get_memory_manager_v2():
    global _memory_manager_v2
    if _memory_manager_v2 is None:
        from app.common.config import RepositoryFactory

        _memory_manager_v2 = RepositoryFactory.get_memory_manager_v2_repository()
    return _memory_manager_v2


def get_message_repository():
    global _message_repository
    if _message_repository is None:
        from app.common.config import RepositoryFactory

        _message_repository = RepositoryFactory.get_message_repository()
    return _message_repository


def get_embedder():
    global _embedder
    if _embedder is None:
        from app.common.config import ChatbotFactory

        _embedder = ChatbotFactory.get_embedding_model("titan")
    return _embedder


class BaseParamsModel(BaseModel):
    pass


class MemoryBlockUpsertParams(BaseParamsModel):
    memory_type: str
    content: str


@tool(
    "memory_block_upsert",
    description="Create or update a unique memory block for the specified type. Each memory type has only one block per user.",
    args_schema=MemoryBlockUpsertParams,
    return_direct=True,
)
async def memory_block_upsert(state: AgentState, input: MemoryBlockUpsertParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())
    embedding = get_embedder().embed_single_text(input.content)
    get_memory_manager_v2().upsert_memory_block(user_id=state.user.id, memory_type=memory_type, content=input.content, embedding=embedding)
    state.memory_blocks = get_memory_manager_v2().get_all_memory_blocks(state.user.id)
    return ActionResult(thought="Upserted memory block", action="memory_block_upsert", result=f"Memory block '{memory_type.value}' updated. Check your memory segment.")


class MemoryBlockReplaceParams(BaseParamsModel):
    memory_type: str
    old_text: str
    new_text: str


@tool(
    "memory_block_replace",
    description="Replace specific text within a memory block. Use this to update specific information in memory blocks.",
    args_schema=MemoryBlockReplaceParams,
    return_direct=True,
)
async def memory_block_replace(state: AgentState, input: MemoryBlockReplaceParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    updated_entry = get_memory_manager_v2().replace_in_memory_block(user_id=state.user.id, memory_type=memory_type, old_text=input.old_text, new_text=input.new_text)

    if not updated_entry:
        return ActionResult(thought="Memory block not found", action="memory_block_replace", result=f"No memory block found for type '{memory_type.value}'")
    state.memory_blocks = get_memory_manager_v2().get_all_memory_blocks(state.user.id)

    return ActionResult(
        thought="Replaced text in memory block", action="memory_block_replace", result=f"Replaced '{input.old_text}' with '{input.new_text}' in {memory_type.value} block"
    )


class MemoryBlockReadParams(BaseParamsModel):
    memory_type: str


@tool(
    "memory_block_read",
    description="Read the entire content of a specific memory block type.",
    args_schema=MemoryBlockReadParams,
    return_direct=True,
)
async def memory_block_read(state: AgentState, input: MemoryBlockReadParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())
    memory_entry = get_memory_manager_v2().read_memory_block(user_id=state.user.id, memory_type=memory_type)
    if not memory_entry:
        return ActionResult(thought="Memory block not found", action="memory_block_read", result=f"No memory block found for type '{memory_type.value}'")
    state.memory_blocks[memory_type.value] = memory_entry
    return ActionResult(thought="Retrieved memory block", action="memory_block_read", result=f"Memory block '{memory_type.value}': {memory_entry.content}")


class MemoryBlockAppendParams(BaseParamsModel):
    memory_type: str
    text: str
    separator: str = Field(default="\n")


@tool(
    "memory_block_append",
    description="Append text to an existing memory block or create a new one if it doesn't exist.",
    args_schema=MemoryBlockAppendParams,
    return_direct=True,
)
async def memory_block_append(state: AgentState, input: MemoryBlockAppendParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    memory_entry = get_memory_manager_v2().append_to_memory_block(user_id=state.user.id, memory_type=memory_type, text=input.text, separator=input.separator)

    # Update state memory blocks
    state.memory_blocks = get_memory_manager_v2().get_all_memory_blocks(state.user.id)
    return ActionResult(
        thought="Appended to memory block", action="memory_block_append", result=f"Appended text to {memory_type.value} block. New size: {len(memory_entry.content)} chars"
    )


class MemoryBlockDeleteParams(BaseParamsModel):
    memory_type: str


@tool(
    "memory_block_delete",
    description="Delete an entire memory block for the specified type.",
    args_schema=MemoryBlockDeleteParams,
    return_direct=True,
)
async def memory_block_delete(state: AgentState, input: MemoryBlockDeleteParams) -> ActionResult:
    memory_type = MemoryType(input.memory_type.lower())

    deleted = get_memory_manager_v2().delete_memory_block(user_id=state.user.id, memory_type=memory_type)

    if not deleted:
        return ActionResult(thought="Memory block not found", action="memory_block_delete", result=f"No memory block found for type '{memory_type.value}' to delete")

    # Update state memory blocks
    state.memory_blocks = get_memory_manager_v2().get_all_memory_blocks(state.user.id)
    return ActionResult(thought="Deleted memory block", action="memory_block_delete", result=f"Deleted memory block for type '{memory_type.value}'")


@tool(
    "memory_blocks_list_all",
    description="Get all memory blocks for the current user, organized by type.",
    args_schema=BaseParamsModel,
    return_direct=True,
)
async def memory_blocks_list_all(state: AgentState, input: BaseParamsModel) -> ActionResult:
    all_blocks = get_memory_manager_v2().get_all_memory_blocks(state.user.id)

    # Update state memory blocks
    state.memory_blocks = all_blocks

    if not all_blocks:
        return ActionResult(thought="No memory blocks found", action="memory_blocks_list_all", result="No memory blocks found for user")

    block_summary = []
    for memory_type, entry in all_blocks.items():
        size = len(entry.content)
        block_summary.append(f"- {memory_type}: {size} chars")
    return ActionResult(thought="Listed all memory blocks", action="memory_blocks_list_all", result="Memory blocks:\n" + "\n".join(block_summary))


# Export memory tools for LLM
memory_tools_v2: list[BaseTool] = [
    memory_block_upsert,
    memory_block_replace,
    memory_block_read,
    # memory_block_append,
    # memory_block_delete,
    # memory_blocks_list_all,
]
