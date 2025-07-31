import asyncio
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.common.models import MemoryManagementConfig, MemoryType, Role, StreamStep
from app.conversation.messages.message_models import AgentVersion


from app.user import User


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

    def serialize(self) -> str:
        """Serialize the memory block to a dictionary"""
        content = self.content
        token_limit = self.memory_type.token_limit
        tokens = len(content) / MemoryManagementConfig.AVERAGE_TOKEN_SIZE
        if tokens > token_limit:
            content = self.content[-token_limit:]
        header = f"\n[Memory Block: {self.memory_type.value} | id={self.id} | max_tokens={token_limit}]\n"
        return header + content


class PaginatedMemoryResult(BaseModel):
    """Represents paginated memory search results"""

    results: list[MemoryEntry]
    page: int
    total_pages: int
    total_count: int
    page_size: int


class ActionResult(BaseModel):
    """Represents the result of an action taken by the agent."""

    timestamp: datetime = Field(default=datetime.now(timezone.utc))
    thought: str
    action: str
    result: str

    def __str__(self) -> str:
        return f"Thought: {self.thought}\nAction: {self.action}\nResult: {self.result}"


class Action(BaseModel):
    """Represents an action that can be performed by the agent."""

    name: str = Field(default="", description="Name of the action to choose")
    description: str = Field(default="", description="Explanation of what this action do")
    params: dict[str, Any] = Field(default={}, description="Input parameters for the action (if any)")


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


class AgentMessage(BaseModel):
    message: str
    role: Role
    timestamp: datetime = Field(default=datetime.now(timezone.utc))

    def get_formatted_prompt(self) -> str:
        ts_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        role_cap = self.role.value.capitalize()
        return f"[{role_cap} - ({ts_str})] {self.message}"


class Phase(Enum):
    NEED_FINAL = "need_final"
    NEED_TOOL = "need_tool"


class AgentState(BaseModel):
    """State for the chat agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    epochs: int = Field(default=0)

    user: User
    messages: list[AgentMessage]
    user_message: str
    agent_message: str = Field(default="")
    prompt: str = Field(default="")
    filepaths: list[str] = Field(default=[])

    # Memory Segments
    system_prompt: str = Field(default="")

    archival_memory: Deque[MemoryEntry] = Field(default=deque([]))
    recall_memory: Deque[MemoryEntry] = Field(default=deque([]))

    # Pagination summary
    current_conversation_history_page: int = Field(default=1)
    current_archival_memory_page: int = Field(default=1)
    total_archival_memory_pages: int = Field(default=1)

    # Multi-step reasoning fields
    phase: Phase = Field(default=Phase.NEED_FINAL)
    thought: AgentThought | None = Field(default=None)
    observations: list[ActionResult] = Field(default=[])

    # Quality assurance fields
    llm_response: str = Field(default="")

    # Error handling
    retry: int = Field(default=0)

    stream_queue: asyncio.Queue = Field(default_factory=lambda: asyncio.Queue(maxsize=0))

    def build_archival_memory(self) -> str:
        """Build the archival memory from the state."""
        if not self.archival_memory:
            return ""

        archival_memory = f"""
Total Pages : {self.total_archival_memory_pages}
Current Page: {self.current_archival_memory_page}\n        
"""

        self.archival_memory.reverse()
        for entry in self.archival_memory:
            archival_memory += entry.serialize()
        return archival_memory

    def build_recall_memory(self) -> str:
        """Build the recall memory from the state."""
        if not self.recall_memory:
            return ""

        recall_memory = ""
        for entry in self.recall_memory:
            recall_memory += entry.serialize()
        return recall_memory

    def build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        page_size = MemoryManagementConfig.CONVERSATION_PAGE_SIZE

        curr_messages = self.messages[-page_size:]
        curr_messages.sort(key=lambda msg: msg.timestamp)

        messages = "\n".join(msg.get_formatted_prompt() for msg in curr_messages)
        return f"""
## CONVERSATION HISTORY
{messages}
"""

    def build_observations(self, curr_page: int = 1) -> str:
        """Build the observation from the state."""
        if not self.observations:
            return ""
        page_size = MemoryManagementConfig.OBSERVATIONS_PAGE_SIZE
        start = (page_size * curr_page) - page_size
        end = start + page_size + 1

        curr_obvs = self.observations[start:end]

        prompt = "==================== PREVIOUS ACTION RESULTS ====================\n"
        for idx, obs in enumerate(curr_obvs):
            prompt += f"### Result {(idx + 1)}.\n"
            prompt += f"{obs}\n"
        prompt += "==================== END OF PREVIOUS ACTION RESULTS ================\n"
        return prompt

    def list_available_temp_files(self) -> str:
        """List the available temporary files from the state."""
        if not self.filepaths:
            return ""
        paths = "\n- ".join(self.filepaths)
        return f"### TEMP FILES\n- {paths}"

    def get_memory_overflow_alert(self) -> str:
        """Check for memory overflow and return alert if needed."""
        alerts = []

        # Calculate current memory usage in characters
        archival_chars = sum(len(entry.content) for entry in self.archival_memory)
        recall_chars = sum(len(entry.content) for entry in self.recall_memory)

        archival_usage = archival_chars / MemoryManagementConfig.ARCHIVAL_MEMORY_LIMIT
        recall_usage = recall_chars / MemoryManagementConfig.RECALL_MEMORY_LIMIT

        if archival_usage >= MemoryManagementConfig.MEMORY_OVERFLOW_THRESHOLD:
            alerts.append(
                f"⚠️ ARCHIVAL MEMORY OVERFLOW: {archival_chars}/"
                f"{MemoryManagementConfig.ARCHIVAL_MEMORY_LIMIT} chars ({archival_usage:.0%}) - "
                f"Consider using archival_memory_evict to remove old memories"
            )

        if recall_usage >= MemoryManagementConfig.MEMORY_OVERFLOW_THRESHOLD:
            alerts.append(
                f"⚠️ RECALL MEMORY OVERFLOW: {recall_chars}/{MemoryManagementConfig.RECALL_MEMORY_LIMIT} chars ({recall_usage:.0%}) - Consider evicting old recall memories"
            )

        return "\n".join(alerts) if alerts else ""

    def build_prompt(self, prompt: str) -> str:
        """Build the prompt from the state."""
        self.prompt = prompt
        self.epochs += 1
        return self.prompt


# Requests
class AgentRequest(BaseModel):
    """Represents a request to an agent."""

    user: "User"
    message_history: list[AgentMessage]
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
