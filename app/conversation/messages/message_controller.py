import json
from typing import Annotated, cast
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from app.chatbot.chatbot_models import AgentMessage, AgentRequest, AgentStreamResponse, StreamStep
from app.chatbot.chatbot_services import ChatbotService
from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders, Role
from app.conversation.conversation_services import ConversationService
from app.conversation.messages.message_models import MessageRequest, MessageResponse, MessageStreamFinalResponse
from app.conversation.messages import Message
from app.conversation.messages.message_services import MessageService
from app.user import User
import logging


class MessageController(BaseController):
    """
    Controller for handling message-related operations.
    This class extends the BaseController to provide message-specific endpoints.
    """

    prefix = "conversations/{conversation_id}/messages"

    @property
    def router(self) -> APIRouter:
        """
        Returns the APIRouter instance for the MessageController.
        This method defines the routes for the message API.
        """

        @self.api_router.post("")
        async def send_message(
            request: Request,
            headers: Annotated[RequestHeaders, Header()],
            conversation_id: UUID,
            message: MessageRequest,
            message_service: MessageService = Depends(ServiceFactory.get_message_service),
            chatbot_service: ChatbotService = Depends(ServiceFactory.get_chatbot_service),
            conversation_service: ConversationService = Depends(ServiceFactory.get_conversation_service),
        ) -> StreamingResponse:
            """
            Endpoint to send a message.
            This endpoint handles the logic for sending a message in a conversation.
            """
            user: User = request.state.user
            logging.info(f"conversation_id: {conversation_id},\nuser: {user.model_dump_json},\nuser request: {message.model_dump_json()}")
            similar_messages = await message_service.get_conversation_history(conversation_id=conversation_id, message_content=message.content)

            async def _handle_streaming_response():
                try:
                    agent_response = ""
                    async for chunk in chatbot_service.ask_async(
                        request=AgentRequest(
                            message_history=[AgentMessage(message=m.content, role=m.role, timestamp=m.updated_at) for m in similar_messages],
                            message=message.content,
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
                    )

                    agent_response = Message(
                        content=agent_response,
                        role=Role.ASSISTANT,
                        conversation_id=conversation_id,
                        model_id=message.model_id,
                        parent_message_id=message.parent_message_id,
                    )
                    conversation = await conversation_service.summarize(
                        conversation_id=conversation_id, user=user, user_message=user_message, agent_response=agent_response
                    )
                    user_message, agent_response = await message_service.add_messages(user=user, user_message=user_message, agent_response=agent_response)
                    if not user_message.id:
                        raise ValueError("Message Id should not be null!")
                    response = MessageStreamFinalResponse(
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
            "",
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

        return self.api_router
