from datetime import datetime, timezone
import enum
from uuid import UUID
from pydantic import BaseModel, Field

from app.common.models import Role


class AgentVersion(enum.Enum):
    """
    Enum representing the different versions of the agent.
    """

    KRISHNA = "krishna"
    KRISHNA_MINI = "krishna-mini"
    KRISHNA_PRO = "krishna-pro"
    KRISHNA_ADVANCE = "krishna-advance"
    KRISHNA_CODE = "krishna-code"


class MessageRequest(BaseModel):
    """
    Represents a request to create a new message.
    """

    content: str
    parent_message_id: UUID | None = None
    model_id: str = "gemini-2.0-flash"
    agent: AgentVersion = Field(default=AgentVersion.KRISHNA_MINI)


class MessageResponse(BaseModel):
    id: UUID
    content: str
    role: Role
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageStreamFinalResponse(BaseModel):
    title: str
    summary: str
    message_id: UUID
    user_message: str
    agent_response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
