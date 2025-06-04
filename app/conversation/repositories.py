from app.common.repositories import BaseRepository

from app.conversation import Conversation
from app.conversation.entities import ConversationEntity
from app.user import User


class ConversationRepository(BaseRepository):
    """
    Repository for managing conversation data.
    This class provides methods to interact with the conversation database.
    """

    def create_conversation(self, user: User) -> Conversation:
        """
        Creates a new conversation for the given user ID.

        Args:
            user_id (str): The ID of the user starting the conversation.

        Returns:
            dict: A dictionary containing the status and message of the operation.
        """
        entity = ConversationEntity(
            user_id=user.id,
            status="active",
        )

        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return Conversation.from_entity(entity)
