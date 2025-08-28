from abc import ABC, abstractmethod
from typing import AsyncGenerator, TYPE_CHECKING, Optional

from app.chatbot.components.conversation_manager import ConversationManager
from app.chatbot.components.tools_manager import ToolsManager
from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.chatbot.messages.message_repositories import MessageRepository
from app.common.vector_embedders import BaseVectorEmbedder

if TYPE_CHECKING:
    from app.chatbot.chatbot_models import StreamChunk

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState


class BaseWorkflowHelper(ABC):
    def __init__(self, chatbot: BaseChatbot, conversation_manager: ConversationManager, tools_manager: ToolsManager) -> None:
        self.chatbot = chatbot
        self.conversation_manager = conversation_manager
        self.tools_manager = tools_manager

    @abstractmethod
    async def prompt_builder(self, state: AgentState) -> AgentState:
        """Build the prompt for the LLM."""
        pass

    @abstractmethod
    async def thinker(self, state: AgentState) -> AgentState:
        """Think about the next step."""
        pass

    @abstractmethod
    async def parse_actions(self, state: AgentState) -> AgentState:
        """Parse the LLM's response."""
        pass

    @abstractmethod
    async def execute_actions(self, state: AgentState) -> AgentState:
        """Execute the actions."""
        pass

    @abstractmethod
    async def persist_message_exchange(self, state: AgentState) -> AgentState:
        """Persist the message exchange."""
        pass

    @abstractmethod
    async def error_handler(self, state: AgentState) -> AgentState:
        """Handle errors."""
        pass


class BaseAgentWorkflow(ABC):
    """Abstract base class for all agent workflows."""

    def __init__(
        self,
        state: AgentState,
        chatbot: BaseChatbot,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        embedder: BaseVectorEmbedder,
        workflow_helper: Optional[BaseWorkflowHelper] = None,
    ):
        self.state = state
        self.chatbot = chatbot
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.embedder = embedder
        self.workflow_helper = workflow_helper

    @abstractmethod
    async def run(self) -> AsyncGenerator["StreamChunk", None]:
        """Run the workflow and yield stream chunks."""
        pass
        yield  # This makes it an async generator

    def _build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        return "\n".join(msg.get_formatted_prompt() for msg in self.state.messages)
