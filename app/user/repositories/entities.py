from sqlalchemy.orm import Mapped, mapped_column
import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.common.entities import BaseEntity


class User(BaseEntity):
    """
    Represents a user in the system.
    """
    __tablename__ = 'users'
    
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        description="Unique Identifier of the User"
    )
    username: Mapped[str] = mapped_column(
        nullable=False,
        unique=True,
        description="Username of the User"
    )