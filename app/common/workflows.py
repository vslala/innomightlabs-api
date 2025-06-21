from abc import ABC, abstractmethod
from typing import AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from app.chatbot.chatbot_models import StreamChunk

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState


class BaseAgentWorkflow(ABC):
    """Abstract base class for all agent workflows."""

    def __init__(self, state: AgentState, chatbot: BaseChatbot):
        self.state = state
        self.chatbot = chatbot

    @abstractmethod
    async def run(self) -> AsyncGenerator["StreamChunk", None]:
        """Run the workflow and yield stream chunks."""
        pass
        yield  # This makes it an async generator

    def _build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        return "\n".join(msg.get_formatted_prompt() for msg in self.state.messages)
