from uuid import UUID, uuid4
from sqlalchemy import select, delete
from app.chatbot.chatbot_models import MemoryEntry
from app.chatbot.workflows.memories.memory_entities import MemoryEntryEntity
from app.common.models import MemoryType
from app.common.repositories import BaseRepository


class MemoryManagerV2(BaseRepository):
    """Memory manager with unique blocks per memory type"""

    def upsert_memory_block(self, user_id: UUID, memory_type: MemoryType, content: str, embedding: list[float] = None) -> MemoryEntry:
        """Create or update unique memory block for given type"""

        # Check if block exists
        stmt = select(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
        existing = self.session.scalar(stmt)

        if existing:
            # Update existing block
            existing.content = content
            if embedding:
                existing.embedding = embedding
            self.session.commit()
            return existing.to_domain()
        else:
            # Create new block
            memory_entry = MemoryEntry(id=uuid4(), user_id=user_id, memory_type=memory_type, content=content, embedding=embedding or [], metadata={})
            entity = MemoryEntryEntity.from_domain(memory_entry)
            self.session.add(entity)
            self.session.commit()
            return memory_entry

    def replace_in_memory_block(self, user_id: UUID, memory_type: MemoryType, old_text: str, new_text: str) -> MemoryEntry | None:
        """Replace specific text within a memory block"""

        stmt = select(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
        entity = self.session.scalar(stmt)

        if not entity:
            return None

        # Perform replacement
        entity.content = entity.content.replace(old_text, new_text)

        self.session.commit()
        return entity.to_domain()

    def read_memory_block(self, user_id: UUID, memory_type: MemoryType) -> MemoryEntry | None:
        """Read entire memory block for given type"""

        stmt = select(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
        entity = self.session.scalar(stmt)
        return entity.to_domain() if entity else None

    def get_all_memory_blocks(self, user_id: UUID) -> dict[str, MemoryEntry]:
        """Get all memory blocks for a user, organized by type"""

        stmt = select(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id)
        entities = self.session.scalars(stmt).all()

        result = {}
        for entity in entities:
            memory_type = MemoryType(entity.memory_type)
            result[memory_type.value] = entity.to_domain()

        return result

    def delete_memory_block(self, user_id: UUID, memory_type: MemoryType) -> bool:
        """Delete entire memory block for given type"""

        stmt = delete(MemoryEntryEntity).where(MemoryEntryEntity.user_id == user_id, MemoryEntryEntity.memory_type == memory_type.value)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0

    def get_memory_block_size(self, user_id: UUID, memory_type: MemoryType) -> int:
        """Get character count of memory block"""

        block = self.read_memory_block(user_id, memory_type)
        return len(block.content) if block else 0

    def append_to_memory_block(self, user_id: UUID, memory_type: MemoryType, text: str, separator: str = "\n") -> MemoryEntry:
        """Append text to existing memory block or create new one"""

        existing_block = self.read_memory_block(user_id, memory_type)

        if existing_block:
            new_content = existing_block.content + separator + text if existing_block.content else text
        else:
            new_content = text

        return self.upsert_memory_block(user_id, memory_type, new_content)
