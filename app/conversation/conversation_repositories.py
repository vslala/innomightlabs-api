from app.common.repositories import BaseRepository

from app.conversation import Conversation
from app.conversation.conversation_entities import ConversationEntity
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
        entity = ConversationEntity(user_id=user.id, status="active", title="New Conversation")

        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return Conversation(id=entity.id, title=entity.title, status=entity.status, created_at=entity.created_at, updated_at=entity.updated_at)

    def fetch_all_conversations_by_user(self, user: User) -> list[Conversation]:
        """Retreives all conversations from the database by user id"""
        conversations = self.session.query(ConversationEntity).filter_by(user_id=user.id).order_by(ConversationEntity.updated_at.desc()).all()
        return [Conversation(id=e.id, title=e.title, status=e.status, created_at=e.created_at, updated_at=e.updated_at) for e in conversations]
