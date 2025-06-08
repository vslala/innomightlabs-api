from app.conversation import Conversation
from app.conversation.conversation_repositories import ConversationRepository
from app.user import User


class ConversationService:
    """
    Service class for managing conversation-related operations.
    This class handles the business logic for starting and managing conversations.
    """

    def __init__(self, conversation_repository: ConversationRepository):
        self.repository = conversation_repository

    async def start_new_conversation(self, user: User) -> Conversation:
        """
        Starts a new conversation for the given user.
        """
        conversation = self.repository.create_conversation(user)
        return conversation

    async def get_all_conversations(self, user: User) -> list[Conversation]:
        conversations = self.repository.fetch_all_conversations_by_user(user=user)
        return conversations
