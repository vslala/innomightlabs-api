from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector

class BaseEntity(DeclarativeBase):
    """
    Base model for all entities in the application.
    This class can be extended by other models to inherit common properties.
    """
    __abstract__ = True