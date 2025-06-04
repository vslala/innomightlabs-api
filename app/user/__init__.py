from datetime import datetime
from typing import Optional, Self
from uuid import UUID
from pydantic import BaseModel

from app.user.entities import UserEntity


class User(BaseModel):
    """Represents a user in the system."""

    id: Optional[UUID] = None
    username: str
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    @classmethod
    def from_entity(cls, entity: UserEntity) -> Self:
        return cls(id=entity.id, username=entity.username, created_at=entity.created_at, updated_at=entity.updated_at)
