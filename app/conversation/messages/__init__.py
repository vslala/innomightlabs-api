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

    id: UUID = Field(default=uuid4())
    content: str
    embedding: Optional[list[float]] = None
    conversation_id: UUID
    role: Role
    parent_message_id: UUID | None = None
    model_id: str = "gemini-2.0-flash"
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
