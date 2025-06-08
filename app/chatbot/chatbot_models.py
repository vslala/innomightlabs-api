import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from app.common.models import Role


class StreamStep(Enum):
    """Enum for different steps in the streaming process."""

    THOUGHT = "thought"
    FINAL_RESPONSE = "final_response"
    END = "end"
    ERROR = "error"


class StreamChunk(TypedDict):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep


class AgentMessage(BaseModel):
    message: str
    role: Role
    timestamp: datetime

    def get_formatted_prompt(self) -> str:
        ts_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        role_cap = self.role.value.capitalize()
        return f"[{role_cap}  - {ts_str}]  {self.message}"


class AgentState(BaseModel):
    """State for the chat agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[AgentMessage]
    user_message: str
    agent_message: str = Field(default="")
    scratchpad: str = Field(default="")
    stream_queue: asyncio.Queue = Field(default_factory=asyncio.Queue)


# Requests
class AgentRequest(BaseModel):
    """
    Represents a request to an agent.
    """

    message_history: list[AgentMessage]
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
