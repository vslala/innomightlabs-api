from datetime import datetime, timezone
from typing import Callable
from unittest.mock import AsyncMock
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.common.controller import BaseController
from app.conversation import Conversation
from app.user import User


def test_start_conversation(
    build_app: Callable[[list[type[BaseController]]], FastAPI],
    mock_conversation_service: AsyncMock,
):
    from app.conversation.conversation_controller import ConversationController

    # 1) Build the app and inject a fake user into request.state.user
    fake_user = User(
        id=uuid.uuid4(),
        username="testuser",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    app = build_app([ConversationController])

    @app.middleware("http")
    async def _inject_user(request: Request, call_next):
        request.state.user = fake_user
        return await call_next(request)

    # 2) Create a “fake” Conversation instance
    fake_conversation = Conversation(
        id=uuid.uuid4(),
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_conversation_service.start_new_conversation.return_value = fake_conversation

    client = TestClient(app)

    # 3) Hit the endpoint
    response = client.post(
        "/api/v1/conversation",
        headers={
            "X-Forwarded-User": fake_user.username,
        },
        json={},
    )
    assert response.status_code == 200, f"Got 422: {response.json()}"

    # 4) Finally, verify the mock was awaited with the correct user
    mock_conversation_service.start_new_conversation.assert_awaited_once_with(user=fake_user)
