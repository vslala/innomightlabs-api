import asyncio
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


from app.chatbot.messages import Message
from app.common.models import MemoryManagementConfig, MemoryType, Role, StreamStep
from app.user import User


T = TypeVar("T")


class AgentVersion(Enum):
    """
    Enum representing the different versions of the agent.
    """

    KRISHNA = "krishna"
    KRISHNA_MINI = "krishna-mini"
    KRISHNA_PRO = "krishna-pro"
    KRISHNA_ADVANCE = "krishna-advance"
    KRISHNA_CODE = "krishna-code"


class MemoryEntry(BaseModel):
    id: UUID
    user_id: UUID
    created_at: datetime = Field(default=datetime.now(timezone.utc))
    memory_type: MemoryType
    content: str
    metadata: dict[str, Any] = Field(default={})
    embedding: list[float] = Field(default=[])
    is_active: bool = Field(default=True)
    evicted_at: datetime | None = Field(default=None)

    def append(self, text: str) -> None:
        """Append text to the memory block"""
        self.content += ("\n" if self.content else "") + text

    def update(self, text: str) -> None:
        """Update the memory block with new text"""
        self.content = text

    def delete(self) -> None:
        """Delete the memory block"""
        self.content = ""

    def serialize(self) -> dict[str, Any]:
        """Serialize the memory block with usage statistics and alerts"""
        content = self.content
        token_limit = self.memory_type.token_limit
        char_limit = token_limit * MemoryManagementConfig.AVERAGE_TOKEN_SIZE
        current_chars = len(content)
        current_tokens = current_chars / MemoryManagementConfig.AVERAGE_TOKEN_SIZE

        usage_pct = (current_tokens / token_limit * 100) if token_limit > 0 else 0

        if current_tokens > token_limit:
            content = content[-char_limit:]

        # Alert if usage >= 70%
        alert = " ⚠️ CLEAN NEEDED" if usage_pct >= 70 else ""

        header = f"\n[{self.memory_type.value.upper()} | {current_chars} chars | {current_tokens:.0f}/{token_limit} tokens ({usage_pct:.1f}%){alert}]\n"
        return {
            "header": header,
            "id": str(self.id),
            "content": content,
        }


class PaginatedResult(BaseModel, Generic[T]):
    """Generic paginated results"""

    results: list[T]
    page: int
    total_pages: int
    total_count: int
    page_size: int


class ActionResult(BaseModel):
    """Represents the result of an action taken by the agent."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thought: str
    action: str
    result: str

    def __str__(self) -> str:
        return f"[{self.action} - {datetime.now(timezone.utc)}] {self.result}"


class Action(BaseModel):
    """Represents an action that can be performed by the agent."""

    name: str = Field(default="", description="Name of the action to choose")
    description: str = Field(default="", description="Explanation of what this action do")
    params: dict[str, Any] = Field(default={}, description="Input parameters for the action (if any)")
    request_heartbeat: bool = Field(default=False, description="Whether to request a heartbeat after this action")
    reason_for_heartbeat: str = Field(default="", description="Reason for requesting heartbeat")


class AgentThought(BaseModel):
    """Represents the thought process of the agent."""

    thought: str = Field(default="", description="Reason behind the action taken")
    action: Action = Field(description="Action associated with this thought")

    def __str__(self) -> str:
        return self.model_dump_json()


class StreamChunk(BaseModel):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep
    step_title: str


class SingleMessage(BaseModel):
    message: str
    role: Role
    timestamp: datetime = Field(default=datetime.now(timezone.utc))

    @classmethod
    def from_message(cls, message: Message) -> "SingleMessage":
        return cls(message=message.content, role=message.role, timestamp=message.created_at)

    def get_formatted_prompt(self) -> str:
        ts_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        role_cap = self.role.value.capitalize()
        return f"[{role_cap} - ({ts_str})] {self.message}"

    def __str__(self) -> str:
        return self.model_dump_json()


class Phase(Enum):
    NEED_FINAL = "need_final"
    NEED_TOOL = "need_tool"
    ERROR = "error"


class AgentState(BaseModel):
    """State for the chat agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    epochs: int = Field(default=0)

    user: User
    conversation_id: UUID
    user_message: str
    agent_message: str = Field(default="")
    prompt: str = Field(default="")
    filepaths: list[str] = Field(default=[])

    # Memory Segments
    system_prompt: str = Field(default="")
    recall_paginated_result: PaginatedResult[MemoryEntry] | None = Field(default=None)
    memory_blocks: dict[MemoryType, MemoryEntry] = Field(default={})

    # Multi-step reasoning fields
    phase: Phase = Field(default=Phase.NEED_FINAL)
    thought: AgentThought | None = Field(default=None)
    thoughts: deque[AgentThought] = Field(default=deque([]))
    observations: list[ActionResult] = Field(default=[])

    # Quality assurance fields
    llm_response: str = Field(default="")

    # Error handling
    retry: int = Field(default=0)

    # Tool call guard
    last_tool_call: tuple[str, str] | None = Field(default=None)  # (tool_name, params_hash)

    stream_queue: asyncio.Queue = Field(default_factory=lambda: asyncio.Queue(maxsize=0))

    def build_observations(self) -> str:
        """Build the observation from the state."""
        if not self.observations:
            return ""
        page_size = MemoryManagementConfig.OBSERVATIONS_PAGE_SIZE
        observations = self.observations[-page_size:]
        return "\n".join([str(obv) for obv in observations])

    def list_available_temp_files(self) -> str:
        """List the available temporary files from the state."""
        if not self.filepaths:
            return ""
        paths = "\n- ".join(self.filepaths)
        return f"### TEMP FILES\n- {paths}"

    def load_and_build_memory_blocks(self) -> str:
        """Build display from in-memory blocks with usage stats and alerts"""
        if not self.memory_blocks:
            return "No memory blocks available."

        blocks_display = []
        for memory_type, entry in self.memory_blocks.items():
            blocks_display.append(entry.serialize())

        return "\n".join(blocks_display)

    def build_conversation_context(self) -> dict[str, Any]:
        """Build conversation context with pagination stats"""
        if not self.recall_paginated_result or not self.recall_paginated_result.results:
            return {}

        stats = f"[Conversation Search: Page {self.recall_paginated_result.page}/{self.recall_paginated_result.total_pages} |\
            {len(self.recall_paginated_result.results)} results |\
                Total: {self.recall_paginated_result.total_count}]"

        context_display = {"stats": stats, "memory": []}
        context = []
        for entry in self.recall_paginated_result.results:
            context.append(entry.serialize())

        context_display.update({"memory": context})
        return context_display

    def build_prompt(self, prompt: str) -> str:
        """Build the prompt from the state."""
        self.prompt = prompt
        self.epochs += 1
        return self.prompt


# Internal Agent Request (used by chatbot service)
class AgentRequest(BaseModel):
    """Represents a request to an agent."""

    user: "User"
    conversation_id: UUID
    message: str
    version: AgentVersion = Field(default=AgentVersion.KRISHNA_MINI)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Responses
class AgentResponse(BaseModel):
    """Represents a response from an agent."""

    response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStreamResponse(BaseModel):
    """Represents a streamed response from an agent."""

    content: str
    step: StreamStep
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def stream_response(self) -> str:
        """Returns a string representation for streaming responses."""
        return f"data: {self.model_dump_json()}\n\n"


class AgentMessageSummary(BaseModel):
    """Represents a title and summary for the given messages"""

    title: str
    summary: str


# Chatbot Request/Response Models (formerly Message models)
class ChatbotRequest(BaseModel):
    """
    Represents a request to send a message to the chatbot.
    """

    content: str
    parent_message_id: UUID | None = None
    model_id: str = "gemini-2.0-flash"
    agent: AgentVersion = Field(default=AgentVersion.KRISHNA_MINI)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageResponse(BaseModel):
    id: UUID
    content: str
    role: Role
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatbotStreamFinalResponse(BaseModel):
    title: str
    summary: str
    message_id: UUID
    user_message: str
    agent_response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
