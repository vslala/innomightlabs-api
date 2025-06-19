from typing import Annotated
from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.chatbot import BaseChatbot
from app.common.config import ChatbotFactory
from app.common.controller import BaseController
from app.common.models import RequestHeaders
from app.chatbot.chatbot_models import AgentRequest


class AgentController(BaseController):
    prefix = "chatbot"

    @property
    def router(self) -> APIRouter:
        """
        Returns the APIRouter instance for the AgentController.
        This method defines the routes for the chatbot API.
        """

        @self.api_router.post(
            "/ask",
            response_class=StreamingResponse,
            response_model=None,
            responses={
                200: {
                    "description": "Server‐Sent Events stream (text/event-stream)",
                    "content": {"text/event-stream": {}},
                }
            },
        )
        async def ask_chatbot(
            request: AgentRequest,
            headers: Annotated[RequestHeaders, Header()],
            chatbot: BaseChatbot = Depends(lambda: ChatbotFactory.create_chatbot("google", "gemini-2.0-flash")),
        ) -> StreamingResponse:
            """
            Endpoint to ask the chatbot a question.
            This endpoint initializes the agentic workflow and processes the user's request.
            """
            # Create service to handle the request
            from app.chatbot.chatbot_services import ChatbotService
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embedding_model = GoogleGenerativeAIEmbeddings(model="embedding-001")
            service = ChatbotService(chatbot=chatbot, embedding_model=embedding_model)

            async def response_streamer():
                async for response in service.ask_async(request):
                    yield f"data: {response.model_dump_json()}\n\n"

            return StreamingResponse(response_streamer(), media_type="text/event-stream")

        return self.api_router
