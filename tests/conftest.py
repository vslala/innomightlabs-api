from typing import Callable, Generator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
import pytest
from app.common.controller import BaseController


@pytest.fixture(scope="module")
def build_app() -> Callable[[list[type[BaseController]]], FastAPI]:
    def _make_app(controllers: list[type[BaseController]]) -> FastAPI:
        """Builds a FastAPI application with the provided controller."""
        app = FastAPI()
        for controller in controllers:
            app.include_router(controller().router)
        return app

    return _make_app


@pytest.fixture
def mock_conversation_service() -> Generator[AsyncMock, None, None]:
    mock_service = AsyncMock()

    async def _return_mock_service() -> AsyncMock:
        return mock_service

    with patch("app.common.config.ServiceFactory.get_conversation_service", new=_return_mock_service):
        yield mock_service


@pytest.fixture
def mock_user_service() -> Generator[AsyncMock, None, None]:
    """
    Patch ServiceFactory.get_user_service with a real async function
    that returns an AsyncMock. This way FastAPI still sees a proper
    coroutine for the dependency, and will bind request-body correctly.
    """
    # 1) Create one AsyncMock which will stand in for the real UserService
    fake_service = AsyncMock()

    # 2) Define a small async "getter" that just returns that fake_service
    async def _fake_get_user_service():
        return fake_service

    # 3) Patch the exact import path that UserController uses
    with patch("app.common.config.ServiceFactory.get_user_service", new=_fake_get_user_service):
        yield fake_service
