from datetime import datetime, timezone
from pydantic import BaseModel, Field


class UserRequest(BaseModel):
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))