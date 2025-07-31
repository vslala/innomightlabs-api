from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.common.models import Role


class Message(BaseModel):
    """
    Represents a message in a conversation.
    This class is the domain model for a message, containing the necessary fields
    """

    id: UUID = Field(default_factory=uuid4)
    content: str
    embedding: Optional[list[float]] = None
    conversation_id: UUID
    role: Role
    parent_message_id: UUID | None = None
    model_id: str = "claude-opus-3"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
