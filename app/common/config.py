from typing import Literal
import os
from sqlalchemy.orm import Session

from app.chatbot import BaseChatbot, ClaudeSonnetChatbot, GeminiChatbot
from app.chatbot.chatbot_models import AgentState
from app.chatbot.chatbot_services import ChatbotService
from app.chatbot.workflows.krishna_advance import KrishnaAdvanceWorkflow
from app.chatbot.workflows.krishna_mini import KrishnaMiniWorkflow
from app.chatbot.workflows.memories.memory_manager import MemoryManager
from app.chatbot.workflows.memories.memory_manager_v2 import MemoryManagerV2
from app.chatbot.workflows.memories.memory_manager_v3 import MemoryManagerV3
from app.common.db_connect import SessionLocal
from app.common.repositories import TransactionManager
from app.common.vector_embedders import BaseVectorEmbedder, LangChainTitanEmbedder
from app.common.workflows import BaseAgentWorkflow
from app.chatbot.chatbot_models import AgentVersion
from app.chatbot.messages.message_repositories import MessageRepository
from app.chatbot.messages.message_services import MessageService
from app.user.user_services import UserService
from app.user.user_repository import UserRepository
from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.chatbot.conversation.conversation_services import ConversationService


# Application configuration settings
class AppConfig:
    """Global application configuration settings"""

    # Tool format: 'yaml' or 'json'
    # Can be overridden by environment variable TOOL_FORMAT
    TOOL_FORMAT = os.getenv("TOOL_FORMAT", "yaml").lower()


def get_session() -> Session:
    return SessionLocal()


# ----- Service and Repository Factories (unchanged) -----
class SessionFactory:
    @staticmethod
    def get_session() -> Session:
        return SessionLocal()


class ServiceFactory:
    @staticmethod
    def get_conversation_service() -> ConversationService:
        return ConversationService(conversation_repository=RepositoryFactory.get_conversation_repository(), embedding_model=ChatbotFactory.get_embedding_model("titan"))

    @staticmethod
    def get_user_service() -> UserService:
        return UserService(RepositoryFactory.get_user_repository())

    @staticmethod
    def get_chatbot_service() -> ChatbotService:
        return ChatbotService(
            chatbot=ChatbotFactory.create_chatbot(owner="anthropic", model_name="sonnet3", temperature=0.0),
            embedding_model=ChatbotFactory.get_embedding_model(name="titan"),
            memory_manager=RepositoryFactory.get_memory_manager_v2_repository(),
        )

    @staticmethod
    def get_message_service() -> MessageService:
        return MessageService(
            RepositoryFactory.get_transaction_manager(),
            RepositoryFactory.get_message_repository(),
            ServiceFactory.get_chatbot_service(),
        )


class RepositoryFactory:
    @staticmethod
    def get_transaction_manager() -> TransactionManager:
        return TransactionManager(session=SessionFactory.get_session())

    @staticmethod
    def get_conversation_repository() -> ConversationRepository:
        return ConversationRepository(session=SessionFactory.get_session())

    @staticmethod
    def get_user_repository() -> UserRepository:
        return UserRepository(session=SessionFactory.get_session())

    @staticmethod
    def get_message_repository() -> MessageRepository:
        return MessageRepository(session=SessionFactory.get_session())

    @staticmethod
    def get_memory_manager_repository() -> MemoryManager:
        return MemoryManager(session=SessionFactory.get_session())

    @staticmethod
    def get_memory_manager_v2_repository() -> MemoryManagerV2:
        return MemoryManagerV2(session=SessionFactory.get_session())

    @staticmethod
    def get_memory_manager_v3_repository() -> MemoryManagerV3:
        return MemoryManagerV3(session=SessionFactory.get_session(), embedder=ChatbotFactory.get_embedding_model("titan"))


class ChatbotFactory:
    @staticmethod
    def create_chatbot(owner: str, model_name: str, temperature: float = 0.0) -> BaseChatbot:
        if owner == "google":
            return GeminiChatbot(model_name=model_name, temperature=temperature)
        elif owner == "anthropic" and model_name == "sonnet3":
            return ClaudeSonnetChatbot()
        raise ValueError(f"Unknown chatbot: {owner} {model_name}")

    @staticmethod
    def get_embedding_model(name: Literal["titan", "gemini"]) -> BaseVectorEmbedder:
        # match name:
        #     case "titan":
        # return LangChainTitanEmbedder()
        # case "gemini":
        #     return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")
        return LangChainTitanEmbedder()


class WorkflowFactory:
    _workflows: dict[AgentVersion, type[BaseAgentWorkflow]] = {
        AgentVersion.KRISHNA_MINI: KrishnaMiniWorkflow,
        AgentVersion.KRISHNA_ADVANCE: KrishnaAdvanceWorkflow,
    }

    @classmethod
    def create_workflow(
        cls,
        version: AgentVersion,
        state: AgentState,
        chatbot: BaseChatbot = ChatbotFactory.create_chatbot(owner="anthropic", model_name="sonnet3"),
    ) -> BaseAgentWorkflow:
        if version not in cls._workflows:
            raise ValueError(f"Unknown workflow version: {version}. Available: {list(cls._workflows.keys())}")
        workflow_class = cls._workflows[version]
        return workflow_class(
            state=state,
            chatbot=chatbot,
            conversation_repository=RepositoryFactory.get_conversation_repository(),
            message_repository=RepositoryFactory.get_message_repository(),
            embedder=ChatbotFactory.get_embedding_model("titan"),
        )

    @classmethod
    def get_available_versions(cls) -> list[AgentVersion]:
        return list(cls._workflows.keys())


class VectorEmbedderFactory:
    @classmethod
    def get_vector_embedder(cls, name: Literal["titan", "gemini"]):
        if name == "titan":
            return LangChainTitanEmbedder()
        else:
            raise ValueError(f"Unknown vector embedder: {name}")
