from functools import lru_cache
import logging

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.chatbot import BaseChatbot, ClaudeSonnetChatbot, GeminiChatbot
from app.chatbot.chatbot_models import AgentState
from app.chatbot.chatbot_services import ChatbotService
from app.chatbot.workflows.krishna import KrishnaWorkflow
from app.chatbot.workflows.krishna_mini import KrishnaMiniWorkflow
from app.common.repositories import TransactionManager
from app.common.workflows import BaseAgentWorkflow
from app.conversation.messages.message_models import AgentVersion
from app.conversation.messages.message_repositories import MessageRepository
from app.conversation.messages.message_services import MessageService
from app.user.user_services import UserService
from app.user.user_repository import UserRepository
from app.conversation.conversation_repositories import ConversationRepository
from app.conversation.conversation_services import ConversationService
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker, Session, scoped_session
import boto3

# set sql alchemy logs to only error
logging.basicConfig()
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)

# 1) Read env vars and build DATABASE_URL
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB")
STAGE = os.getenv("STAGE", "local").lower()


def make_db_url():
    if STAGE == "dev":
        token = boto3.client("rds", region_name=AWS_REGION).generate_db_auth_token(
            DBHostname=POSTGRES_HOST,
            Port=int(POSTGRES_PORT),
            DBUsername=POSTGRES_USER,
        )
        return URL.create(
            "postgresql+psycopg2",
            username=POSTGRES_USER,
            password=token,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            query={"sslmode": "require"},
        )
    else:
        return URL.create(
            "postgresql+psycopg2",
            username=POSTGRES_USER,
            password=os.getenv("POSTGRES_PASSWORD"),
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
        )


# 1) Build engine once
engine = create_engine(make_db_url(), pool_pre_ping=True, future=True)

# 2) If IAM, inject fresh token on each new connection
if STAGE == "dev":

    @event.listens_for(engine, "do_connect")
    def refresh_token(dialect, conn_rec, cargs, cparams):
        fresh = make_db_url()
        cparams.update(
            {
                "username": fresh.username,
                "password": fresh.password,
            }
        )
        return dialect.connect(*cargs, **cparams)


# 3) Session factory
SessionLocal = scoped_session(
    sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
)


def get_session():
    return SessionLocal()


class SessionFactory:
    @staticmethod
    def get_session() -> Session:
        return SessionLocal()


class ServiceFactory:
    @staticmethod
    @lru_cache
    def get_conversation_service() -> ConversationService:
        conversation_service = ConversationService(
            conversation_repository=RepositoryFactory.get_conversation_repository(), chatbot_service=ServiceFactory.get_chatbot_service()
        )
        return conversation_service

    @staticmethod
    @lru_cache
    def get_user_service() -> UserService:
        user_service = UserService(RepositoryFactory.get_user_repository())
        return user_service

    @staticmethod
    @lru_cache
    def get_chatbot_service() -> ChatbotService:
        chatbot_service = ChatbotService(
            chatbot=ChatbotFactory.create_chatbot(owner="anthropic", model_name="sonnet3", temperature=0.0),
            embedding_model=ChatbotFactory.get_embedding_model(),
        )
        return chatbot_service

    @staticmethod
    @lru_cache
    def get_message_service() -> MessageService:
        message_service = MessageService(
            RepositoryFactory.get_transaction_manager(),
            RepositoryFactory.get_message_repository(),
            ServiceFactory.get_chatbot_service(),
        )
        return message_service


class RepositoryFactory:
    @staticmethod
    @lru_cache
    def get_transaction_manager() -> TransactionManager:
        return TransactionManager(session=SessionFactory.get_session())

    @staticmethod
    @lru_cache
    def get_conversation_repository() -> ConversationRepository:
        conversation_repository = ConversationRepository(session=SessionFactory.get_session())
        return conversation_repository

    @staticmethod
    @lru_cache
    def get_user_repository() -> UserRepository:
        user_repository = UserRepository(session=SessionFactory.get_session())
        return user_repository

    @staticmethod
    @lru_cache
    def get_message_repository() -> MessageRepository:
        message_repository = MessageRepository(session=SessionFactory.get_session())
        return message_repository


class ChatbotFactory:
    @staticmethod
    def create_chatbot(owner: str, model_name: str, temperature: float = 0.0) -> BaseChatbot:
        if owner == "google":
            return GeminiChatbot(model_name=model_name, temperature=temperature)

        elif owner == "anthropic" and model_name == "sonnet3":
            return ClaudeSonnetChatbot()

        raise ValueError(f"Unknown chatbot: {owner} {model_name}")

    @staticmethod
    def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
        return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")


class WorkflowFactory:
    """Factory class to create different agent workflows."""

    _workflows: dict[AgentVersion, type[BaseAgentWorkflow]] = {AgentVersion.KRISHNA_MINI: KrishnaMiniWorkflow, AgentVersion.KRISHNA: KrishnaWorkflow}

    @classmethod
    def create_workflow(cls, version: AgentVersion, state: AgentState, chatbot: BaseChatbot) -> BaseAgentWorkflow:
        """Create a workflow instance based on version."""
        if version not in cls._workflows:
            raise ValueError(f"Unknown workflow version: {version}. Available: {list(cls._workflows.keys())}")

        workflow_class = cls._workflows[version]
        return workflow_class(state, chatbot)

    @classmethod
    def get_available_versions(cls) -> list[AgentVersion]:
        """Get list of available workflow versions."""
        return list(cls._workflows.keys())
