from datetime import datetime
from typing import Self
from uuid import UUID
from pydantic import BaseModel
from app.conversation.entities import ConversationEntity


class Conversation(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, entity: ConversationEntity) -> Self:
        """
        Converts a ConversationEntity to a Conversation model.

        Args:
            entity (ConversationEntity): The entity to convert.

        Returns:
            Conversation: The converted Conversation model.
        """
        return cls(id=entity.id, created_at=entity.created_at, updated_at=entity.updated_at, status=entity.status)
