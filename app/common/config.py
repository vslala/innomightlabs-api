from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.chatbot import BaseChatbot, GeminiChatbot
from app.chatbot.chatbot_services import ChatbotService
from app.common.repositories import TransactionManager
from app.conversation.messages.message_repositories import MessageRepository
from app.conversation.messages.message_services import MessageService
from app.user.user_services import UserService
from app.user.user_repository import UserRepository
from app.conversation.conversation_repositories import ConversationRepository
from app.conversation.conversation_services import ConversationService
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session

# 1) Read env vars once, build the URL once
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASS = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB")

if not all([POSTGRES_USER, POSTGRES_PASS, POSTGRES_DB]):
    raise RuntimeError("Make sure POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB are set")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASS}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# 2) Create the engine once
engine = create_engine(DATABASE_URL, echo=True, future=True)

# 3) Create a Session factory once
session_factory = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # often useful in web apps
    future=True,
)

# 4) wrap in `scoped_session` for thread‐local sessions
#    To call get_session() from different threads and for
#    each thread to automatically re‐use its own session (instead of always
#    having to pass the session object around), do this:
SessionLocal = scoped_session(session_factory=session_factory)


class SessionFactory:
    @staticmethod
    def get_session() -> Session:
        return SessionLocal()


class ServiceFactory:
    @staticmethod
    @lru_cache
    def get_conversation_service() -> ConversationService:
        conversation_service = ConversationService(conversation_repository=RepositoryFactory.get_conversation_repository())
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
            chatbot=ChatbotFactory.create_chatbot(owner="google", model_name="gemini-2.0-flash", temperature=0.0),
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
        return GeminiChatbot(model_name=model_name, temperature=temperature)

    @staticmethod
    def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
        return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07")
