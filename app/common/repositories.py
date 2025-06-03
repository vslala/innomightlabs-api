from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel
from sqlalchemy import DateTime, String, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector

class BaseRepository:
    """Base class for all repositories."""
    def __init__(self, session: Session):
        """
        Every derived “Repository” gets a SQLAlchemy Session injected.
        """
        self.session = session

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()
        


class Conversation(BaseModel):
    """
    Represents a conversation in the system.
    """
    __tablename__ = 'conversations'
    
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        description="Unique Identifier of the Conversation"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        description="ID of the User who owns the Conversation"
    )
    title: Mapped[str] = mapped_column(
        nullable=False,
        description="Title of the Conversation"
    )
    summary: Mapped[str] = mapped_column(
        nullable=True,
        description="Summary of the Conversation"
    )
    summary_embeddings: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=True,
        description="Embeddings of the Conversation summary for search and retrieval"
    )
    status: Mapped[str] = mapped_column(
        nullable=False,
        default='active',
        description="Status of the Conversation (e.g., active, archived)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        description="Timestamp when the Conversation was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        description="Timestamp when the Conversation was last updated"
    )
    

class Message(BaseModel):
    """
    Represents a message in a conversation.
    """ 
    __tablename__ = 'messages'
    
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default_factory=uuid.uuid4,
        description="Unique Identifier of the Message"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        description="ID of the Conversation to which this Message belongs"
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        description="ID of the User who sent the Message"
    )
    role: Mapped[str] = mapped_column(
        nullable=False,
        description="Role of the sender (e.g., user, assistant)"
    )
    model_id: Mapped[str] = mapped_column(
        nullable=False,
        default="gemini-2.0-flash",
        description="ID of the model used to generate the Message"
    )
    message: Mapped[str] = mapped_column(
        nullable=False,
        description="Content of the Message"
    )
    message_embeddings: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=True,
        description="Embeddings of the Message content for search and retrieval"
    )
    parent_message_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        description="ID of the parent Message in the conversation thread"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        description="Timestamp when the Message was created"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        description="Timestamp when the Conversation was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        description="Timestamp when the Conversation was last updated"
    )