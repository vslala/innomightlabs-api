from enum import Enum
from typing import ClassVar
from uuid import uuid4
from pydantic import BaseModel
from loguru import logger
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
    CONTEXT_LENGTH: ClassVar[int] = 8000
    AVERAGE_TOKEN_SIZE: ClassVar[int] = 4

    SYSTEM_INSTRUCTIONS_SIZE: ClassVar[int] = int(CONTEXT_LENGTH * 0.30)
    WORKING_CONTEXT_SIZE: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    CONVERSATION_HISTORY_SIZE: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    RECALL_MEMORY_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    BUFFER_TOKENS: ClassVar[int] = int(CONTEXT_LENGTH * 0.10)

    CONVERSATION_PAGE_SIZE: ClassVar[int] = 100
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
    CONVERSATION_HISTORY = ("conversation_history", int(MemoryManagementConfig.CONTEXT_LENGTH * 0.20))

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


class MemoryBlock(BaseModel):
    title: str = Field(..., description="title of the block")
    type: MemoryType
    size: int = Field(default=1000, description="token length for the block")
    content: str = Field(default="", description="content of the block")

    def serialize(self) -> str:
        """Serialize the memory block to a string."""
        logger.info(f"[{self.type}] Total content size: {len(self.content)}")
        if len(self.content) > self.size:
            logger.info(f"Content Stripped: {self.content[0 : len(self.content) - self.size]}")
            self.content = self.content[: -self.size]

        return self.model_dump_json()
