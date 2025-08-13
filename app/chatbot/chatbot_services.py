from typing import AsyncGenerator

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentRequest, AgentState, AgentStreamResponse
from app.chatbot.workflows.memories.memory_manager_v2 import MemoryManagerV2
from app.common.vector_embedders import BaseVectorEmbedder


class ChatbotService:
    def __init__(self, chatbot: BaseChatbot, embedding_model: BaseVectorEmbedder, memory_manager: MemoryManagerV2) -> None:
        self.chatbot = chatbot
        self.embedding_model = embedding_model
        self.memory_manager = memory_manager

    """
    Service class for handling chatbot-related operations.
    This class contains methods for interacting with the chatbot.
    """

    async def ask_async(self, request: AgentRequest) -> AsyncGenerator[AgentStreamResponse, None]:
        """Send a message to the chatbot and return the response."""
        from app.common.config import WorkflowFactory

        state = AgentState(user=request.user, conversation_id=request.conversation_id, user_message=request.message)

        workflow = WorkflowFactory.create_workflow(
            version=request.version,
            state=state,
        )
        async for chunk in workflow.run():
            yield AgentStreamResponse(content=chunk.content, step=chunk.step, timestamp=request.timestamp)
