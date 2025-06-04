from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar

from fastapi import APIRouter


class BaseController(ABC):
    """
    Base controller class for the application.
    This class can be extended by other controllers to inherit common properties and methods.
    """

    prefix: ClassVar[str]
    tags: ClassVar[list[str | Enum] | None] = None

    def __init__(self) -> None:
        """
        Initialize the controller with the request object.
        """
        self.api_router = APIRouter(prefix=f"/api/v1/{self.prefix}" if self.prefix else "", tags=self.tags if self.tags else [self.prefix], redirect_slashes=False)

    @property
    @abstractmethod
    def router(self) -> APIRouter:
        """Abstract property must be implemented by subclasses to return the APIRouter instance."""
        raise NotImplementedError("Subclasses must implement the router property.")
