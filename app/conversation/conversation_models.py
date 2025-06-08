from datetime import datetime, timezone
from typing import Self
from uuid import UUID
from pydantic import BaseModel

from app.conversation import Conversation


class ConversationRequest(BaseModel):
    """
    Request model for conversation operations.
    This model is used to send the necessary data for starting or managing a conversation.
    Currently, it is empty but can be extended in the future.
    """

    pass


class ConversationResponse(BaseModel):
    """
    Response model for conversation operations.
    This model is used to return the status and message of a conversation operation.
    """

    id: UUID
    title: str
    summary: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_conversation(cls, conversation: Conversation) -> Self:
        return cls(
            id=conversation.id,
            title=conversation.title,
            summary=conversation.summary,
            status=conversation.status,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


class ConversationRepositoryDTO(BaseModel):
    id: UUID
    title: str
    summary: str
    summary_embedding: list[float]
    status: str
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)
