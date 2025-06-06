from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.common.entities import BaseEntity


class UserEntity(BaseEntity):
    """
    Represents a user in the system.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, doc="Unique Identifier of the User")
    username: Mapped[str] = mapped_column(nullable=False, unique=True, doc="Username of the User")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now(timezone.utc), doc="Timestamp when the User was created")
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        doc="Timestamp when the Conversation was last updated",
    )
