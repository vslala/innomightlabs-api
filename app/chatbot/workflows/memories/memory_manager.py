from uuid import UUID

from sqlalchemy import func, select, update
from app.chatbot.chatbot_models import MemoryEntry, PaginatedMemoryResult
from app.chatbot.workflows.memories.memory_entities import MemoryEntryEntity
from app.common.models import MemoryManagementConfig
from app.common.repositories import BaseRepository
from app.conversation.messages.message_entities import MessageEntity


class MemoryManager(BaseRepository):
    def search(self, user_id: UUID, embeddings: list[float], top_k: int = 3) -> list[MemoryEntry]:
        sub_q = (
            select(MemoryEntryEntity)
            .where(MemoryEntryEntity.user_id == user_id)
            .order_by(MemoryEntryEntity.embedding.l2_distance(embeddings), MemoryEntryEntity.created_at.desc())
            .limit(top_k)
        )

        stmt = update(MemoryEntryEntity).where(MemoryEntryEntity.id.in_(select(sub_q.c.id))).values(is_active=True).returning(MemoryEntryEntity)

        result = self.session.execute(stmt)
        # scalars() gives ORM‐mapped objects
        entities = result.scalars().all()
        self.session.commit()
        return [ent.to_domain() for ent in entities]

    def update_memory(self, domain: MemoryEntry) -> None:
        """Upserts MemoryEntryEntity from a domain model"""

        memory_entity = MemoryEntryEntity.from_domain(domain)
        self.session.merge(memory_entity)
        self.session.commit()

    def update_memory_batch(self, domains: list[MemoryEntry]) -> None:
        """Upserts a batch of MemoryEntryEntity from domain models"""

        memory_entities = [MemoryEntryEntity.from_domain(domain) for domain in domains]
        self.session.bulk_save_objects(memory_entities)
        self.session.commit()

    def evict_memory(self, entry_id: UUID) -> None:
        """Makes the memory in-active"""

        self.session.query(MemoryEntryEntity).filter(MemoryEntryEntity.id == entry_id).delete()
        self.commit()

    def evict_memory_batch(self, ids: list[UUID]) -> None:
        """Makes a batch of memories in-active"""
        self.session.query(MemoryEntryEntity).filter(MemoryEntryEntity.id.in_(ids)).delete()
        self.commit()

    def read(self, user_id: UUID, limit: int = 100) -> list[MemoryEntry]:
        """Reads the top N latest entries"""

        # 1) pick the IDs we want
        subq = select(MemoryEntryEntity.id).where(MemoryEntryEntity.user_id == user_id).order_by(MemoryEntryEntity.created_at.desc()).limit(limit).subquery()

        # 2) update + returning
        stmt = (
            update(MemoryEntryEntity).where(MemoryEntryEntity.id.in_(select(subq.c.id))).values(is_active=True).returning(MemoryEntryEntity)  # ← ask SQL to spill back full rows
        )

        result = self.session.execute(stmt)
        # scalars() gives ORM‐mapped objects
        entities = result.scalars().all()
        self.session.commit()

        return [ent.to_domain() for ent in entities]

    def search_paginated(self, user_id: UUID, embeddings: list[float], page: int = 1) -> PaginatedMemoryResult:
        """Search memory with pagination support"""

        page_size = MemoryManagementConfig.MEMORY_SEARCH_PAGE_SIZE
        offset = (page - 1) * page_size

        # Get total count
        count_stmt = select(func.count(MemoryEntryEntity.id)).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.is_active)
        total_count = self.session.scalar(count_stmt) or 0
        total_pages = (total_count + page_size - 1) // page_size  # Ceiling division

        # Get paginated results
        sub_q = (
            select(MemoryEntryEntity)
            .where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.is_active)
            .order_by(MemoryEntryEntity.embedding.l2_distance(embeddings), MemoryEntryEntity.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        stmt = update(MemoryEntryEntity).where(MemoryEntryEntity.id.in_(select(sub_q.c.id))).values(is_active=True).returning(MemoryEntryEntity)
        result = self.session.execute(stmt)
        # scalars() gives ORM‐mapped objects
        entities = result.scalars().all()
        self.session.commit()

        results = [entity.to_domain() for entity in entities]
        return PaginatedMemoryResult(results=results, page=page, total_pages=total_pages, total_count=total_count, page_size=page_size)

    async def search_conversation_paginated_by_user_id_and_embeddings(self, user_id: UUID, embeddings: list[float], page: int = 1) -> PaginatedMemoryResult:
        from app.chatbot.chatbot_models import MemoryEntry, MemoryType
        from app.common.models import MemoryManagementConfig
        from sqlalchemy import func

        page_size = MemoryManagementConfig.MEMORY_SEARCH_PAGE_SIZE
        offset = (page - 1) * page_size

        # Get total count
        count_stmt = select(func.count(MessageEntity.id)).where(MessageEntity.sender_id == user_id)
        total_count = self.session.scalar(count_stmt) or 0
        total_pages = (total_count + page_size - 1) // page_size

        distance_expr = MessageEntity.message_embedding.l2_distance(embeddings)
        similarity_expr = (1 / (1 + distance_expr)).label("confidence")

        # Get paginated results
        stmt = (
            select(MessageEntity, similarity_expr)
            .where(MessageEntity.sender_id == user_id)
            .order_by(MessageEntity.message_embedding.l2_distance(embeddings), MessageEntity.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        rows = self.session.scalars(stmt).all()
        results = [
            MemoryEntry(
                id=e.id,
                user_id=user_id,
                memory_type=MemoryType.RECALL,
                content=e.message,
                embedding=e.message_embedding,
                created_at=e.created_at,
            )
            for e in rows
        ]

        return PaginatedMemoryResult(results=results, page=page, total_pages=total_pages, total_count=total_count, page_size=page_size)
