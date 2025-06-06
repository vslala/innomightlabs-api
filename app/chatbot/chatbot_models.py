import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TypedDict

from pydantic import BaseModel, Field


class StreamStep(Enum):
    """Enum for different steps in the streaming process."""

    THIKING = "thinking"
    FINAL_RESPONSE = "final_response"
    END = "end"
    ERROR = "error"


class StreamChunk(TypedDict):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep


class AgentState(TypedDict):
    """State for the chat agent workflow."""

    messages: list[str]
    user_message: str
    agent_message: Optional[str]
    scratchpad: Optional[str]
    stream_queue: Optional[asyncio.Queue[StreamChunk]]


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

    def stream_response(self) -> str:
        """
        Returns a string representation of the request for streaming.
        This method is used to format the request for streaming responses.
        """
        return f"data: {self.model_dump_json()}\n\n"
