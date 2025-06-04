from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request

from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders
from app.conversation import Conversation
from app.conversation.models import ConversationResponse
from app.conversation.services import ConversationService
from app.user import User


class ConversationController(BaseController):
    prefix = "conversation"

    @property
    def router(self) -> APIRouter:
        """
        Returns the APIRouter instance for the ConversationController.
        This method defines the routes for the conversation API.
        """

        @self.api_router.post(
            "",
            response_model=ConversationResponse,
            responses={200: {"description": "Conversation started successfully"}},
        )
        async def start_conversation(request: Request, headers: Annotated[RequestHeaders, Header()], conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service)) -> ConversationResponse:
            """
            Endpoint to start a new conversation.
            This endpoint initializes a new conversation session.
            """
            user: User = request.state.user
            conversation: Conversation = conversation_service.start_new_conversation(user=user)
            return ConversationResponse(**conversation.model_dump())

        return self.api_router
