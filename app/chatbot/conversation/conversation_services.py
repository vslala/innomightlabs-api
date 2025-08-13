from uuid import UUID
from app.chatbot.conversation import Conversation
from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.common.vector_embedders import BaseVectorEmbedder
from app.user import User


class ConversationService:
    """
    Service class for managing conversation-related operations.
    This class handles the business logic for starting and managing conversations.
    """

    def __init__(self, conversation_repository: ConversationRepository, embedding_model: BaseVectorEmbedder):
        self.repository = conversation_repository
        self.embedder = embedding_model

    async def find_by_id(self, id: UUID) -> Conversation:
        """
        Finds a conversation by its ID.
        """
        conversation = self.repository.find_conversation_by_id(id)
        return conversation

    async def start_new_conversation(self, user: User) -> Conversation:
        """
        Starts a new conversation for the given user.
        """
        conversation = self.repository.create_conversation(user)
        return conversation

    async def get_all_conversations(self, user: User) -> list[Conversation]:
        conversations = self.repository.fetch_all_conversations_by_user(user=user)
        return conversations

    async def delete_conversation(self, conversation_id: UUID) -> None:
        await self.repository.delete_conversation(conversation_id)
