from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """
    Represents a response from an agent.
    """

    response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
