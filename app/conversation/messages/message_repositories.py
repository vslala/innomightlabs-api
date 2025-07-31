from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.common.repositories import BaseRepository
from sqlalchemy.orm import Session

from app.conversation.messages import Message
from app.conversation.messages.message_entities import MessageEntity


class MessageRepository(BaseRepository):
    def create_message(self, session: Session, message: Message, sender_id: UUID) -> Message:
        """
        Create or update a message in the database using upsert.

        :param session: SQLAlchemy session to use for the transaction.
        :param message: Message object to be created or updated.
        :return: The created/updated Message object.
        """
        stmt = insert(MessageEntity).values(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=sender_id,
            role=message.role,
            model_id=message.model_id,
            message=message.content,
            message_embedding=message.embedding,
            parent_message_id=message.parent_message_id,
        )

        # On conflict, update the message content and embedding
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "message": stmt.excluded.message,
                "message_embedding": stmt.excluded.message_embedding,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        session.execute(stmt)
        session.flush()

        # Fetch the created/updated entity to get timestamps
        message_entity = session.get(MessageEntity, message.id)
        if message_entity:
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
        entity_messages = self.session.query(MessageEntity).filter(MessageEntity.conversation_id == conversation_id).order_by(MessageEntity.created_at.asc()).all()
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

    async def search_all_by_user_id_and_embeddings(self, user_id: UUID, embeddings: list[float], top_k: int = 3) -> list[Message]:
        stmt = (
            select(MessageEntity)
            .where(MessageEntity.sender_id == user_id)
            .order_by(MessageEntity.message_embedding.l2_distance(embeddings), MessageEntity.created_at.desc())
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

    async def delete_message(self, message_id: UUID) -> None:
        """
        Delete a message by its ID.

        :param message_id: The ID of the message to delete.
        """
        self.session.query(MessageEntity).filter(MessageEntity.id == message_id).delete()
        self.session.commit()
