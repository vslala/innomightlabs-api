from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class AgentState(TypedDict):
    """State for the chat agent workflow."""

    messages: list[str]
    user_message: str
    agent_message: str
    scratchpad: str  # Optional scratchpad for intermediate thoughts or notes
    stream_queue: Any


class StreamStep(Enum):
    """Enum for different steps in the streaming process."""

    THIKING = "thinking"
    FINAL_RESPONSE = "final_response"


class StreamChunk(TypedDict):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep



# Requests
class AgentRequest(BaseModel):
    """
    Represents a request to an agent.
    """

    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Responses
class AgentResponse(BaseModel):
    """
    Represents a response from an agent.
    """

    response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStreamResponse(BaseModel):
    """
    Represents a streamed response from an agent.
    """

    content: str
    step: StreamStep
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))