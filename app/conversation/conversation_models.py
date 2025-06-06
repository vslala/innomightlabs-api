from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


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
    status: str
    created_at: datetime
    updated_at: datetime
