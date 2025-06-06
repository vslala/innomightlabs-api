from uuid import UUID
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
