from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class Conversation(BaseModel):
    id: UUID
    title: str = Field(default="")
    summary: str = Field(default="")
    status: str
    created_at: datetime
    updated_at: datetime
