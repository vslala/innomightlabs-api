import asyncio
from datetime import datetime, timezone
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from app.common.models import Role, StreamStep
from app.conversation.messages.message_models import AgentVersion


class StreamChunk(TypedDict):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep
    step_title: str | None


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

    # Multi-step reasoning fields
    analysis: str = Field(default="")
    plan: str = Field(default="")
    reasoning: str = Field(default="")
    synthesis: str = Field(default="")

    # Quality assurance fields
    draft_response: str = Field(default="")
    evaluation: str = Field(default="")
    needs_refinement: bool = Field(default=True)
    refinement_count: int = Field(default=0)

    stream_queue: asyncio.Queue = Field(default_factory=asyncio.Queue)


# Requests
class AgentRequest(BaseModel):
    """
    Represents a request to an agent.
    """

    message_history: list[AgentMessage]
    message: str
    version: AgentVersion = Field(default=AgentVersion.KRISHNA_MINI)
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


class AgentMessageSummary(BaseModel):
    """Represents a title and summary for the given messages"""

    title: str
    summary: str
