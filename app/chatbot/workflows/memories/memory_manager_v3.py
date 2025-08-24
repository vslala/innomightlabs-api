from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.chatbot.chatbot_models import MemoryEntry, PaginatedResult
from app.chatbot.workflows.memories.memory_entities import MemoryEntryEntity
from app.common.models import MemoryType
from app.common.repositories import BaseRepository
from app.common.vector_embedders import BaseVectorEmbedder


class MemoryManagerV3(BaseRepository):
    """Advance Paginated Memory Manager"""

    def __init__(self, session: Session, embedder: BaseVectorEmbedder):
        super().__init__(session)
        self.embedder = embedder
        self.page_size = 100  # tokens

    def _convert_to_token_count(self, text: str) -> int:
        """Convert text length to approximate token count (1 token ≈ 4 characters)"""
        return len(text) // 4

    def append(self, memory_entry: MemoryEntry) -> PaginatedResult[MemoryEntry]:
        """Appends the text to the given memory block. If the last page of memory block is full, it creates a new page and appends the text to it"""
        total_pages = (
            self.session.query(MemoryEntryEntity).filter(MemoryEntryEntity.user_id == memory_entry.user_id, MemoryEntryEntity.memory_type == memory_entry.memory_type.value).count()
        )
        stmt = (
            select(MemoryEntryEntity)
            .where(MemoryEntryEntity.user_id == memory_entry.user_id, MemoryEntryEntity.memory_type == memory_entry.memory_type.value)
            .order_by(MemoryEntryEntity.created_at.desc())
            .limit(1)
        )
        entity = self.session.scalar(stmt)
        if not entity:
            # memory block is empty, create a new page
            memory_entry.metadata["page_size"] = self._convert_to_token_count(memory_entry.content)
            entity = MemoryEntryEntity.from_domain(memory_entry)
            self.session.add(entity)
            self.session.commit()
            return PaginatedResult(results=[entity.to_domain()], total_pages=1, page=1, total_count=self._convert_to_token_count(memory_entry.content), page_size=self.page_size)

        existing_page_tokens = self._convert_to_token_count(entity.content)
        new_content_tokens = self._convert_to_token_count(memory_entry.content)
        if existing_page_tokens + new_content_tokens > self.page_size:
            # create new page
            memory_entry.metadata["page_size"] = self._convert_to_token_count(memory_entry.content)
            entity = MemoryEntryEntity.from_domain(memory_entry)
            self.session.add(entity)
            self.session.commit()
            return PaginatedResult(
                results=[entity.to_domain()],
                total_pages=total_pages + 1,
                page=total_pages + 1,
                total_count=self._convert_to_token_count(memory_entry.content),
                page_size=self.page_size,
            )
        else:
            entity.content += memory_entry.content
            entity.embedding = self.embedder.embed_single_text(entity.content)
            self.session.commit()
            return PaginatedResult(
                results=[entity.to_domain()], total_pages=total_pages, page=total_pages, total_count=self._convert_to_token_count(entity.content), page_size=self.page_size
            )

    def replace(self, user_id: UUID, memory_type: MemoryType, page: int, old_txt: str, new_txt: str) -> PaginatedResult[MemoryEntry]:
        """Replaces the text in the specified page of the memory block."""
        total_pages = self.session.query(MemoryEntryEntity).filter(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value).count()
        stmt = (
            select(MemoryEntryEntity)
            .where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
            .order_by(MemoryEntryEntity.created_at.asc())
            .offset(page - 1)
            .limit(1)
        )
        entity = self.session.scalar(stmt)
        if not entity:
            raise ValueError(f"Provide page: {page} does not exists.")

        entity.content = entity.content.replace(old_txt, new_txt)
        entity.embedding = self.embedder.embed_single_text(entity.content)
        self.session.commit()
        return PaginatedResult(results=[entity.to_domain()], total_pages=total_pages, page=page, total_count=self._convert_to_token_count(entity.content), page_size=self.page_size)

    def evict(self, user_id: UUID, memory_type: MemoryType, page: int, text: str) -> PaginatedResult[MemoryEntry]:
        return self.replace(user_id, memory_type, page, text, "")

    def read(self, user_id: UUID, memory_type: MemoryType, query: str, page: int = 1) -> PaginatedResult[MemoryEntry]:
        """Reads the memory block and returns the text"""
        embeddings = self.embedder.embed_single_text(query)

        # Get total count of matching pages
        total_count_stmt = select(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
        total_pages = len(self.session.scalars(total_count_stmt).all())

        if total_pages == 0:
            return PaginatedResult(results=[], total_pages=0, page=page, total_count=0, page_size=self.page_size)

        # Get the specific page requested
        stmt = (
            select(MemoryEntryEntity)
            .where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
            .order_by(MemoryEntryEntity.embedding.cosine_distance(embeddings))
            .offset(page - 1)
            .limit(1)
        )
        entity = self.session.scalar(stmt)

        if not entity:
            raise ValueError(f"Page {page} does not exist.")

        return PaginatedResult(results=[entity.to_domain()], total_pages=total_pages, page=page, total_count=self._convert_to_token_count(entity.content), page_size=self.page_size)
