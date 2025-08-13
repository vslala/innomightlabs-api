from enum import Enum
from typing import ClassVar
from uuid import uuid4
from pydantic import BaseModel

from pydantic import Field


UUID_FIELD = Field(
    description="Unique Identifier of the Resource",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
)

UUID_FIELD_WITH_DEFAULT = Field(
    description="Unique Identifier of the Resource",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    default_factory=lambda: str(uuid4()),
)


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class StreamStep(Enum):
    """Enum for different steps in the streaming process."""

    ANALYSIS = "analysis"
    PLANNING = "planning"
    REASONING = "reasoning"
    SYNTHESIS = "synthesis"
    DRAFT = "draft"
    EVALUATION = "evaluation"
    REFINEMENT = "refinement"
    FINAL_RESPONSE = "final_response"
    END = "end"
    ERROR = "error"


# Requests
class RequestHeaders(BaseModel):
    x_forwarded_user: str


class MemoryManagementConfig(BaseModel):
    CONTEXT_LENGTH: ClassVar[int] = 2000
    AVERAGE_TOKEN_SIZE: ClassVar[int] = 4

    BASE_PROMPT_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.30)
    INTUITIVE_KNOWLEDGE_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    ARCHIVAL_MEMORY_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    RECALL_MEMORY_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    BUFFER_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.10)

    # Memory limits based on token allocation
    ARCHIVAL_MEMORY_LIMIT: ClassVar[int] = ARCHIVAL_MEMORY_TOKENS // AVERAGE_TOKEN_SIZE
    RECALL_MEMORY_LIMIT: ClassVar[int] = RECALL_MEMORY_TOKENS // AVERAGE_TOKEN_SIZE

    CONVERSATION_PAGE_SIZE: ClassVar[int] = 20
    OBSERVATIONS_PAGE_SIZE: ClassVar[int] = 10
    MEMORY_SEARCH_PAGE_SIZE: ClassVar[int] = 10
    MEMORY_OVERFLOW_THRESHOLD: ClassVar[float] = 0.8


class MemoryType(Enum):
    PERSONA = ("persona", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.05))
    USER_PROFILE = ("user_profile", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.05))
    RECALL = ("recall", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.20))
    SUMMARY = ("summary", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.05))
    ARCHIVAL = ("archival", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.01))
    SYSTEM = ("system", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.30))

    def __new__(cls, memory_type: str, token_limit: int):
        obj = object.__new__(cls)
        obj._value_ = memory_type
        return obj

    def __init__(self, memory_type: str, token_limit: int) -> None:
        self.memory_type = memory_type
        self.token_limit = token_limit

    def value_str(self) -> str:
        """Return the string representation of the memory type."""
        return self.memory_type
