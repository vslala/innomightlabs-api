from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request

from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders
from app.conversation import Conversation
from app.conversation.conversation_models import ConversationResponse
from app.conversation.conversation_services import ConversationService
from app.user import User


class ConversationController(BaseController):
    prefix = "conversations"

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
        async def start_conversation(
            request: Request,
            headers: Annotated[RequestHeaders, Header()],
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> ConversationResponse:
            """
            Endpoint to start a new conversation.
            This endpoint initializes a new conversation session.
            """
            user: User = request.state.user
            conversation: Conversation = await conversation_service.start_new_conversation(user=user)
            return ConversationResponse(**conversation.model_dump())

        @self.api_router.get(
            "",
            response_model=list[Conversation],
            responses={200: {"description": "Returns a list of conversation for the given user id in reverse chronological order"}},
        )
        async def get_conversations(
            request: Request,
            headers: Annotated[RequestHeaders, Header()],
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> list[ConversationResponse]:
            user = request.state.user
            all_conversations = await conversation_service.get_all_conversations(user=user)
            return [ConversationResponse.from_conversation(conversation=conversation) for conversation in all_conversations]

        @self.api_router.delete(
            "/{conversation_id}",
            responses={204: {"description": "Conversation deleted successfully"}},
            status_code=204,
        )
        async def delete_conversation(
            conversation_id: UUID,
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> None:
            await conversation_service.delete_conversation(conversation_id=conversation_id)

        return self.api_router
