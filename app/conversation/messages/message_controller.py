import json
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from app.chatbot.chatbot_models import AgentRequest, AgentStreamResponse, StreamStep
from app.chatbot.chatbot_services import ChatbotService
from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders
from app.conversation.messages.message_models import MessageRequest, MessageResponse
from app.conversation.messages import Message
from app.conversation.messages.message_services import MessageService
from app.user import User
import logging


class MessageController(BaseController):
    """
    Controller for handling message-related operations.
    This class extends the BaseController to provide message-specific endpoints.
    """

    prefix = "conversation/{conversation_id}/message"

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
            conversation_id: str,
            message: MessageRequest,
            message_service: MessageService = Depends(ServiceFactory.get_message_service),
            chatbot_service: ChatbotService = Depends(ServiceFactory.get_chatbot_service),
        ) -> StreamingResponse:
            """
            Endpoint to send a message.
            This endpoint handles the logic for sending a message in a conversation.
            """
            user: User = request.state.user
            logging.info(f"conversation_id: {conversation_id},\nuser: {user.model_dump_json},\nuser request: {message.model_dump_json()}")

            async def _handle_streaming_response():
                try:
                    agent_response = ""
                    async for chunk in chatbot_service.ask_async(request=AgentRequest(message=message.content)):
                        agent_response = agent_response.join([chunk.content])
                        yield chunk.stream_response()

                    user_message = Message(
                        content=message.content,
                        role="user",
                        conversation_id=conversation_id,
                        model_id=message.model_id,
                        parent_message_id=message.parent_message_id,
                    )

                    agent_response = Message(
                        content=agent_response,
                        role="assistant",
                        conversation_id=conversation_id,
                        model_id=message.model_id,
                        parent_message_id=message.parent_message_id,
                    )

                    user_message, agent_response = await message_service.add_messages(user=user, user_message=user_message, agent_response=agent_response)
                    if not user_message.id:
                        raise ValueError("Message Id should not be null!")
                    response = MessageResponse(
                        message_id=user_message.id,
                        user_message=user_message.content,
                        agent_response=agent_response.content,
                    )

                    yield AgentStreamResponse(content=response.model_dump_json(), step=StreamStep.END).stream_response()
                except Exception as e:
                    yield AgentStreamResponse(content=json.dumps({"error": str(e)}), step=StreamStep.ERROR).stream_response()

            return StreamingResponse(_handle_streaming_response(), media_type="text/event-stream")

        return self.api_router
