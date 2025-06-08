from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class Conversation(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
