from uuid import UUID

from sqlalchemy import select
from app.common.repositories import BaseRepository
from sqlalchemy.orm import Session

from app.conversation.messages import Message
from app.conversation.messages.message_entities import MessageEntity


class MessageRepository(BaseRepository):
    def create_message(self, session: Session, message: Message, sender_id: UUID) -> Message:
        """
        Create a new message in the database.

        :param session: SQLAlchemy session to use for the transaction.
        :param message: Message object to be created.
        :return: The created Message object.
        """
        message_entity = MessageEntity(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=sender_id,
            role=message.role,
            model_id=message.model_id,
            message=message.content,
            message_embedding=message.embedding,
            parent_message_id=message.parent_message_id,
        )
        session.add(message_entity)
        session.flush()

        message.id = message_entity.id
        message.created_at = message_entity.created_at
        message.updated_at = message_entity.updated_at

        return message

    def fetch_all_by_conversation_id_and_embedding(self, conversation_id: UUID, embedding: list[float], top_k: int = 10):
        stmt = (
            select(MessageEntity)
            .where(MessageEntity.conversation_id == conversation_id)
            .order_by(MessageEntity.message_embedding.l2_distance(embedding), MessageEntity.updated_at.desc())
            .limit(top_k)
        )

        entities = self.session.scalars(stmt).all()
        return [
            Message(
                id=e.id,
                conversation_id=e.conversation_id,
                role=e.role,
                model_id=e.model_id,
                content=e.message,
                embedding=e.message_embedding,
                parent_message_id=e.parent_message_id,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in entities
        ]

    async def fetch_all_messages(self, conversation_id: UUID) -> list[Message]:
        entity_messages = self.session.query(MessageEntity).filter(MessageEntity.conversation_id == conversation_id).order_by(MessageEntity.created_at).all()
        return [
            Message(
                id=e.id,
                conversation_id=e.conversation_id,
                content=e.message,
                embedding=e.message_embedding,
                role=e.role,
                parent_message_id=e.parent_message_id,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in entity_messages
        ]
