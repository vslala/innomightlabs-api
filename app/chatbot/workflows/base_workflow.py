from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import AgentState, StreamChunk


class BaseAgentWorkflow(ABC):
    """Abstract base class for all agent workflows."""

    def __init__(self, state: AgentState, chatbot: BaseChatbot):
        self.state = state
        self.chatbot = chatbot

    @abstractmethod
    def run(self) -> AsyncGenerator[StreamChunk, None]:
        """Run the workflow and yield stream chunks."""
        pass

    def _build_conversation_history(self) -> str:
        """Build the conversation history from the state."""
        return "\n".join(msg.get_formatted_prompt() for msg in self.state.messages)
