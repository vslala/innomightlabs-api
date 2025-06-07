from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, Field

from app.chatbot.chatbot_models import StreamStep
from app.common.models import Role


class MessageRequest(BaseModel):
    """
    Represents a request to create a new message.
    """

    content: str
    parent_message_id: UUID | None = None
    model_id: str = "gemini-2.0-flash"


class MessageResponse(BaseModel):
    id: UUID
    content: str
    role: Role
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageStreamFinalResponse(BaseModel):
    message_id: UUID
    user_message: str
    agent_response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageStreamResponse(BaseModel):
    """
    Represents a streamed response from an agent.
    """

    content: str
    step: StreamStep
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
