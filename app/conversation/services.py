from app.conversation import Conversation
from app.conversation.repositories import ConversationRepository
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
        Starts a new conversation for the given user ID.

        Args:
            user_id (str): The ID of the user starting the conversation.

        Returns:
            dict: A dictionary containing the status and message of the operation.
        """
        conversation = self.repository.create_conversation(user)
        return conversation
