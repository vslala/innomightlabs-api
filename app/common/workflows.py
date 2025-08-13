from abc import ABC, abstractmethod
from typing import AsyncGenerator, TYPE_CHECKING

from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.chatbot.messages.message_repositories import MessageRepository
from app.common.vector_embedders import BaseVectorEmbedder

if TYPE_CHECKING:
    from app.chatbot.chatbot_models import StreamChunk

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState


class BaseAgentWorkflow(ABC):
    """Abstract base class for all agent workflows."""

    def __init__(
        self, state: AgentState, chatbot: BaseChatbot, conversation_repository: ConversationRepository, message_repository: MessageRepository, embedder: BaseVectorEmbedder
    ):
        self.state = state
        self.chatbot = chatbot
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.embedder = embedder

    @abstractmethod
    async def run(self) -> AsyncGenerator["StreamChunk", None]:
        """Run the workflow and yield stream chunks."""
        pass
        yield  # This makes it an async generator

    def _build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        return "\n".join(msg.get_formatted_prompt() for msg in self.state.messages)
