from datetime import datetime, timezone
from typing import Callable
from unittest.mock import AsyncMock
import uuid
from fastapi import FastAPI

from fastapi.testclient import TestClient
from app.common.controller import BaseController
from app.user.controller import UserController
from app.user.models import UserCreateRequest
from app.user import User


def test_create_user_returns_200(build_app: Callable[[list[type[BaseController]]], FastAPI], mock_user_service: AsyncMock):
    expected_user = User(
        id=uuid.uuid4(),
        username="testuser",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_service.add_user.return_value = expected_user
    app = build_app([UserController])
    client = TestClient(app)

    payload = UserCreateRequest(username="testuser").model_dump()
    response = client.post("/api/v1/user", json=payload)

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["username"] == "testuser"

    mock_user_service.add_user.assert_awaited_once_with(UserCreateRequest(username="testuser"))
