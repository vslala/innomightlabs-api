import json
from typing import Annotated, cast
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.chatbot.chatbot_models import AgentRequest, AgentStreamResponse, StreamStep, ChatbotRequest, MessageResponse, ChatbotStreamFinalResponse
from app.chatbot.chatbot_services import ChatbotService
from app.chatbot.conversation import Conversation
from app.chatbot.conversation.conversation_models import ConversationResponse
from app.chatbot.conversation.conversation_services import ConversationService
from app.chatbot.messages.message_services import MessageService
from app.chatbot.messages import Message
from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders, Role
from app.user import User
import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


class ChatbotController(BaseController):
    prefix = "chatbot"

    @property
    def router(self) -> APIRouter:
        """
        Returns the APIRouter instance for the ChatbotController.
        This method defines the routes for the chatbot API.
        """

        @self.api_router.post(
            "/conversations",
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

        @self.api_router.post("/conversations/{conversation_id}/messages")
        async def send_message(
            request: Request,
            headers: Annotated[RequestHeaders, Header()],
            conversation_id: UUID,
            message: ChatbotRequest,
            message_service: MessageService = Depends(ServiceFactory.get_message_service),
            chatbot_service: ChatbotService = Depends(ServiceFactory.get_chatbot_service),
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> StreamingResponse:
            """
            Endpoint to send a message to the chatbot.
            This endpoint handles the logic for sending a message in a conversation.
            """
            user: User = request.state.user
            logger.info(f"conversation_id: {conversation_id},\nuser: {user.model_dump_json},\nuser request: {message.model_dump_json()}")

            async def _handle_streaming_response():
                try:
                    agent_response = ""
                    async for chunk in chatbot_service.ask_async(
                        request=AgentRequest(
                            user=user,
                            conversation_id=conversation_id,
                            message=message.content,
                            version=message.agent,
                        )
                    ):
                        print(chunk.content, end="")
                        if chunk.step is StreamStep.FINAL_RESPONSE:
                            agent_response = "".join([agent_response, chunk.content])
                        yield chunk.stream_response()

                    user_message = Message(
                        content=message.content,
                        role=Role.USER,
                        conversation_id=conversation_id,
                        model_id=message.model_id,
                        parent_message_id=message.parent_message_id,
                        created_at=message.timestamp,
                        updated_at=message.timestamp,
                    )

                    agent_response = Message(
                        content=agent_response,
                        role=Role.ASSISTANT,
                        conversation_id=conversation_id,
                        model_id=message.model_id,
                        parent_message_id=message.parent_message_id,
                    )
                    logger.info(f"user_message={user_message.model_dump_json()}\nagent_response={agent_response.model_dump_json()}")
                    if not user_message.id:
                        raise ValueError("Message Id should not be null!")

                    conversation = await conversation_service.find_by_id(id=conversation_id)
                    response = ChatbotStreamFinalResponse(
                        title=conversation.title,
                        summary=conversation.summary,
                        message_id=user_message.id,
                        user_message=user_message.content,
                        agent_response=agent_response.content,
                    )
                    yield AgentStreamResponse(content=response.model_dump_json(), step=StreamStep.END).stream_response()
                except Exception as e:
                    yield AgentStreamResponse(content=json.dumps({"error": str(e)}), step=StreamStep.ERROR).stream_response()
                    raise e

            return StreamingResponse(_handle_streaming_response(), media_type="text/event-stream")

        @self.api_router.get(
            "/conversations/{conversation_id}/messages",
            response_model=list[MessageResponse],
            responses={
                200: {
                    "description": "List of all messages for the given Conversation Id",
                    "content": {"application/json": {}},
                }
            },
        )
        async def get_all_messages(conversation_id: UUID, message_service: MessageService = Depends(ServiceFactory.get_message_service)):
            messages = await message_service.get_all_messages(conversation_id=conversation_id)
            return [
                MessageResponse(
                    id=cast(UUID, e.id),
                    content=e.content,
                    role=e.role,
                )
                for e in messages
            ]

        @self.api_router.get(
            "/conversations",
            response_model=list[ConversationResponse],
            responses={
                200: {
                    "description": "List of all conversations",
                    "content": {"application/json": {}},
                }
            },
        )
        async def get_all_conversations(
            request: Request,
            headers: Annotated[RequestHeaders, Header()],
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ):
            user: User = request.state.user
            conversations = await conversation_service.get_all_conversations(user=user)
            return [
                ConversationResponse(
                    id=cast(UUID, e.id),
                    title=e.title,
                    summary=e.summary,
                    status=e.status,
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
                for e in conversations
            ]

        @self.api_router.delete(
            "/conversations/{conversation_id}",
            responses={204: {"description": "Conversation deleted successfully"}},
            status_code=204,
        )
        async def delete_conversation(
            conversation_id: UUID,
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> None:
            await conversation_service.delete_conversation(conversation_id=conversation_id)

        return self.api_router
