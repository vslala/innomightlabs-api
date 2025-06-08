from uuid import UUID
from app.common.exceptions import NotFoundException
from app.common.repositories import BaseRepository

from app.conversation import Conversation
from app.conversation.conversation_entities import ConversationEntity
from app.conversation.conversation_models import ConversationRepositoryDTO
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
        return [
            Conversation(id=e.id, title=e.title, status=e.status, summary=e.summary or "", created_at=e.created_at, updated_at=e.updated_at)
            for e in conversations
        ]

    def find_conversation_by_id(self, conversation_id: UUID) -> Conversation:
        entity = self.session.query(ConversationEntity).filter_by(id=conversation_id).first()
        if not entity:
            raise NotFoundException(f"Conversation with ID: {conversation_id} was not found!")
        return Conversation(
            id=entity.id, title=entity.title, status=entity.status, summary=entity.summary or "", created_at=entity.created_at, updated_at=entity.updated_at
        )

    def update_conversation(self, dto: ConversationRepositoryDTO) -> Conversation:
        print(f"[DTO]\n{dto}")
        entity = self.session.query(ConversationEntity).filter_by(id=dto.id).first()
        assert entity
        entity.id = dto.id
        entity.title = dto.title
        entity.summary = dto.summary
        entity.status = dto.status
        entity.summary_embedding = dto.summary_embedding

        self.session.commit()
        return Conversation(**dto.model_dump())
