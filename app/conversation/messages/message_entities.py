from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from app.common.entities import BaseEntity


class MessageEntity(BaseEntity):
    """
    Represents a message in a conversation.
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, doc="Unique Identifier of the Message")
    conversation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, doc="ID of the Conversation to which this Message belongs")
    sender_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=True, doc="ID of the User who sent the Message")
    role: Mapped[str] = mapped_column(nullable=False, doc="Role of the sender (e.g., user, assistant, system)")
    model_id: Mapped[str] = mapped_column(nullable=False, default="gemini-2.0-flash", doc="ID of the model used to generate the Message")
    message: Mapped[str] = mapped_column(nullable=False, doc="Content of the Message")
    message_embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False, doc="Embeddings of the Message content for search and retrieval")
    parent_message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=True, doc="ID of the parent Message in the conversation thread")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc), doc="Timestamp when the Message was created")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), doc="Timestamp when the Message was last updated")
