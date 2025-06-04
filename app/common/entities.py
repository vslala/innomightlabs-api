from sqlalchemy.orm import DeclarativeBase


class BaseEntity(DeclarativeBase):
    """
    Base model for all entities in the application.
    This class can be extended by other models to inherit common properties.
    """

    __abstract__ = True
