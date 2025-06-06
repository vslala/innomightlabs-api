from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Message(BaseModel):
    """
    Represents a message in a conversation.
    This class is the domain model for a message, containing the necessary fields
    """

    id: Optional[UUID] = None
    content: str
    embedding: Optional[list[float]] = None
    conversation_id: str
    role: str
    parent_message_id: UUID | None = None
    model_id: str = "gemini-2.0-flash"
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
