import asyncio
from typing import AsyncGenerator

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.chatbot import BaseChatbot
from app.chatbot.chat_agent_workflow import AgenticWorkflow
from app.chatbot.chatbot_models import AgentRequest, AgentState, AgentStreamResponse, StreamChunk


class ChatbotService:
    def __init__(self, chatbot: BaseChatbot, embedding_model: GoogleGenerativeAIEmbeddings) -> None:
        self.chatbot = chatbot
        self.embedding_model = embedding_model

    """
    Service class for handling chatbot-related operations.
    This class contains methods for interacting with the chatbot.
    """

    async def ask_async(self, request: AgentRequest) -> AsyncGenerator[AgentStreamResponse, None]:
        """Send a message to the chatbot and return the response."""
        stream = asyncio.Queue[StreamChunk]()
        state = AgentState(
            messages=request.message_history,
            user_message=request.message,
            agent_message="",
            scratchpad="",
            stream_queue=stream,
        )
        workflow = AgenticWorkflow(
            state=state,
            chatbot=self.chatbot,
        )
        async for chunk in workflow.run():
            yield AgentStreamResponse(content=chunk["content"], step=chunk["step"])

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text."""
        from asyncio import to_thread

        return await to_thread(self.embedding_model.embed_query, text, output_dimensionality=1536)
