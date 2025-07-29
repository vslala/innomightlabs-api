from sqlalchemy import TEXT, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, BOOLEAN
from datetime import datetime, timezone
from typing import Any, Self
from uuid import UUID

from app.chatbot.chatbot_models import MemoryEntry, MemoryType
from app.common.entities import BaseEntity


class MemoryEntryEntity(BaseEntity):
    """Represents Memory Entry"""

    __tablename__ = "memory_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    memory_type: Mapped[str] = mapped_column(TEXT, nullable=False)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    meta_info: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    evicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the Memory Entry was evicted",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        doc="Timestamp when the Memory Entry was created",
    )

    @classmethod
    def from_domain(cls, model: MemoryEntry) -> Self:
        return cls(
            id=model.id,
            user_id=model.user_id,
            memory_type=model.memory_type.value,
            content=model.content,
            metadata=model.metadata,
            embedding=model.embedding,
            is_active=model.is_active,
            evicted_at=model.evicted_at,
            created_at=model.created_at,
        )

    def to_domain(self) -> MemoryEntry:
        return MemoryEntry(
            id=self.id,
            user_id=self.user_id,
            memory_type=MemoryType(self.memory_type),
            content=self.content,
            metadata=self.meta_info,
            embedding=self.embedding,
            is_active=self.is_active,
            evicted_at=self.evicted_at,
            created_at=self.created_at,
        )
