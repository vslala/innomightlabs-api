from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector

from app.common.entities import BaseEntity


class ConversationEntity(BaseEntity):
    """
    Represents a conversation in the system.
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, doc="Unique Identifier of the Conversation")
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, doc="ID of the User who owns the Conversation")
    title: Mapped[str] = mapped_column(nullable=True, doc="Title of the Conversation")
    summary: Mapped[str] = mapped_column(nullable=True, doc="Summary of the Conversation")
    summary_embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True, doc="Embeddings of the Conversation summary for search and retrieval")
    status: Mapped[str] = mapped_column(nullable=False, default="active", doc="Status of the Conversation (e.g., active, archived)")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc), doc="Timestamp when the Conversation was created")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), doc="Timestamp when the Conversation was last updated")
