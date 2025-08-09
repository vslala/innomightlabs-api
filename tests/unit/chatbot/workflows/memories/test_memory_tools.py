import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from app.chatbot.workflows.helpers.tools.memory_tools import (
    memory_block_upsert,
    memory_block_replace,
    memory_block_read,
    memory_block_append,
    memory_block_delete,
    memory_blocks_list_all,
    MemoryBlockUpsertParams,
    MemoryBlockReplaceParams,
    MemoryBlockReadParams,
    MemoryBlockAppendParams,
    MemoryBlockDeleteParams,
    BaseParamsModel,
)
from app.chatbot.chatbot_models import AgentState, MemoryEntry, ActionResult, PaginatedMemoryResult
from app.common.models import MemoryType
from app.user import User


@pytest.fixture
def mock_user():
    return User(id=uuid4(), username="testuser")


@pytest.fixture
def mock_agent_state(mock_user):
    return AgentState(user=mock_user, messages=[], user_message="test message", memory_blocks={})


@pytest.fixture
def mock_memory_entry():
    return MemoryEntry(id=uuid4(), user_id=uuid4(), memory_type=MemoryType.PERSONA, content="Test content", embedding=[0.1, 0.2, 0.3], metadata={})


@pytest.fixture
def mock_memory_manager():
    return Mock()


@pytest.fixture
def mock_embedder():
    embedder = Mock()
    embedder.embed_single_text.return_value = [0.1, 0.2, 0.3]
    return embedder


class TestMemoryBlockUpsert:
    @pytest.mark.asyncio
    async def test_upsert_new_memory_block(self, mock_agent_state, mock_memory_manager, mock_embedder, mock_memory_entry):
        with (
            patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager),
            patch("app.chatbot.workflows.memories.memory_tools.get_embedder", return_value=mock_embedder),
        ):
            mock_memory_manager.upsert_memory_block.return_value = mock_memory_entry
            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: mock_memory_entry}

            params = MemoryBlockUpsertParams(memory_type="persona", content="New persona content")
            result = await memory_block_upsert.coroutine(mock_agent_state, params)

            assert isinstance(result, ActionResult)
            assert result.action == "memory_block_upsert"
            assert "persona" in result.result
            mock_memory_manager.upsert_memory_block.assert_called_once()
            mock_embedder.embed_single_text.assert_called_once_with("New persona content")

    @pytest.mark.asyncio
    async def test_upsert_updates_state_memory_blocks(self, mock_agent_state, mock_memory_manager, mock_embedder, mock_memory_entry):
        with (
            patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager),
            patch("app.chatbot.workflows.memories.memory_tools.get_embedder", return_value=mock_embedder),
        ):
            mock_memory_manager.upsert_memory_block.return_value = mock_memory_entry
            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: mock_memory_entry}

            params = MemoryBlockUpsertParams(memory_type="persona", content="Test content")
            await memory_block_upsert.coroutine(mock_agent_state, params)

            assert MemoryType.PERSONA in mock_agent_state.memory_blocks
            mock_memory_manager.get_all_memory_blocks.assert_called_once_with(mock_agent_state.user.id)


class TestMemoryBlockReplace:
    @pytest.mark.asyncio
    async def test_replace_existing_text(self, mock_agent_state, mock_memory_manager, mock_memory_entry):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            updated_entry = MemoryEntry(
                id=mock_memory_entry.id,
                user_id=mock_memory_entry.user_id,
                memory_type=mock_memory_entry.memory_type,
                content="Updated content",
                embedding=mock_memory_entry.embedding,
                metadata=mock_memory_entry.metadata,
            )
            mock_memory_manager.replace_in_memory_block.return_value = updated_entry
            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: updated_entry}

            params = MemoryBlockReplaceParams(memory_type="persona", old_text="old", new_text="new")
            result = await memory_block_replace.coroutine(mock_agent_state, params)

            assert result.action == "memory_block_replace"
            assert "old" in result.result and "new" in result.result
            mock_memory_manager.replace_in_memory_block.assert_called_once_with(user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA, old_text="old", new_text="new")

    @pytest.mark.asyncio
    async def test_replace_memory_block_not_found(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.replace_in_memory_block.return_value = None

            params = MemoryBlockReplaceParams(memory_type="persona", old_text="old", new_text="new")
            result = await memory_block_replace.coroutine(mock_agent_state, params)

            assert "no memory block found" in result.result.lower()


class TestMemoryBlockRead:
    @pytest.mark.asyncio
    async def test_read_existing_memory_block(self, mock_agent_state, mock_memory_manager, mock_memory_entry):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.read_memory_block.return_value = mock_memory_entry

            params = MemoryBlockReadParams(memory_type="persona")
            result = await memory_block_read.coroutine(mock_agent_state, params)

            assert result.action == "memory_block_read"
            assert mock_memory_entry.content in result.result
            mock_memory_manager.read_memory_block.assert_called_once_with(user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA)

    @pytest.mark.asyncio
    async def test_read_nonexistent_memory_block(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.read_memory_block.return_value = None

            params = MemoryBlockReadParams(memory_type="persona")
            result = await memory_block_read.coroutine(mock_agent_state, params)

            assert "no memory block found" in result.result.lower()


class TestMemoryBlockAppend:
    @pytest.mark.asyncio
    async def test_append_to_existing_block(self, mock_agent_state, mock_memory_manager, mock_memory_entry):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            appended_entry = MemoryEntry(
                id=mock_memory_entry.id,
                user_id=mock_memory_entry.user_id,
                memory_type=mock_memory_entry.memory_type,
                content=mock_memory_entry.content + "\nAppended text",
                embedding=mock_memory_entry.embedding,
                metadata=mock_memory_entry.metadata,
            )
            mock_memory_manager.append_to_memory_block.return_value = appended_entry
            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: appended_entry}

            params = MemoryBlockAppendParams(memory_type="persona", text="Appended text")
            result = await memory_block_append.coroutine(mock_agent_state, params)

            assert result.action == "memory_block_append"
            assert "chars" in result.result
            mock_memory_manager.append_to_memory_block.assert_called_once_with(
                user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA, text="Appended text", separator="\n"
            )

    @pytest.mark.asyncio
    async def test_append_with_custom_separator(self, mock_agent_state, mock_memory_manager, mock_memory_entry):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.append_to_memory_block.return_value = mock_memory_entry
            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: mock_memory_entry}

            params = MemoryBlockAppendParams(memory_type="persona", text="Appended text", separator=" | ")
            await memory_block_append.coroutine(mock_agent_state, params)

            mock_memory_manager.append_to_memory_block.assert_called_once_with(
                user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA, text="Appended text", separator=" | "
            )


class TestMemoryBlockDelete:
    @pytest.mark.asyncio
    async def test_delete_existing_block(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.delete_memory_block.return_value = True
            mock_memory_manager.get_all_memory_blocks.return_value = {}

            params = MemoryBlockDeleteParams(memory_type="persona")
            result = await memory_block_delete.coroutine(mock_agent_state, params)

            assert result.action == "memory_block_delete"
            assert "deleted" in result.result.lower()
            mock_memory_manager.delete_memory_block.assert_called_once_with(user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_block(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.delete_memory_block.return_value = False

            params = MemoryBlockDeleteParams(memory_type="persona")
            result = await memory_block_delete.coroutine(mock_agent_state, params)

            assert "no memory block found" in result.result.lower()


class TestMemoryBlocksListAll:
    @pytest.mark.asyncio
    async def test_list_all_with_blocks(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            persona_entry = MemoryEntry(id=uuid4(), user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA, content="Persona content", embedding=[], metadata={})
            recall_entry = MemoryEntry(id=uuid4(), user_id=mock_agent_state.user.id, memory_type=MemoryType.RECALL, content="Recall content", embedding=[], metadata={})

            mock_memory_manager.get_all_memory_blocks.return_value = {MemoryType.PERSONA: persona_entry, MemoryType.RECALL: recall_entry}

            params = BaseParamsModel()
            result = await memory_blocks_list_all.coroutine(mock_agent_state, params)

            assert result.action == "memory_blocks_list_all"
            assert "persona" in result.result.lower()
            assert "recall" in result.result.lower()
            assert "chars" in result.result
            assert len(mock_agent_state.memory_blocks) == 2

    @pytest.mark.asyncio
    async def test_list_all_no_blocks(self, mock_agent_state, mock_memory_manager):
        with patch("app.chatbot.workflows.memories.memory_tools.get_memory_manager_v2", return_value=mock_memory_manager):
            mock_memory_manager.get_all_memory_blocks.return_value = {}

            params = BaseParamsModel()
            result = await memory_blocks_list_all.coroutine(mock_agent_state, params)

            assert "no memory blocks found" in result.result.lower()


class TestPaginationFunctionality:
    """Test pagination-related functionality in memory tools"""

    @pytest.mark.asyncio
    async def test_paginated_memory_result_structure(self, mock_agent_state):
        """Test PaginatedMemoryResult structure and pagination stats"""

        memory_entries = [
            MemoryEntry(id=uuid4(), user_id=mock_agent_state.user.id, memory_type=MemoryType.RECALL, content=f"Memory content {i}", embedding=[], metadata={}) for i in range(5)
        ]

        paginated_result = PaginatedMemoryResult(results=memory_entries[:3], page=1, total_pages=2, total_count=5, page_size=3)

        mock_agent_state.recall_paginated_result = paginated_result
        context = mock_agent_state.build_conversation_context()

        assert "Page 1/2" in context["stats"]
        assert "3 results" in context["stats"]
        assert "Total: 5" in context["stats"]

    @pytest.mark.asyncio
    async def test_memory_block_serialization_with_pagination_info(self, mock_agent_state):
        """Test memory block serialization includes usage stats for pagination decisions"""

        large_content = "x" * 1000
        memory_entry = MemoryEntry(id=uuid4(), user_id=mock_agent_state.user.id, memory_type=MemoryType.PERSONA, content=large_content, embedding=[], metadata={})

        serialized = memory_entry.serialize()

        assert "chars" in serialized["header"]
        assert "tokens" in serialized["header"]
        assert "PERSONA" in serialized["header"]

    @pytest.mark.asyncio
    async def test_conversation_history_pagination(self, mock_agent_state):
        """Test conversation history respects pagination limits"""
        from app.chatbot.chatbot_models import AgentMessage
        from app.common.models import Role
        from datetime import datetime, timezone

        for i in range(10):
            message = AgentMessage(message=f"Message {i}", role=Role.USER, timestamp=datetime.now(timezone.utc))
            mock_agent_state.messages.append(message)

        history = mock_agent_state.build_conversation_history()
        assert len(history) <= 5

    @pytest.mark.asyncio
    async def test_observations_pagination(self, mock_agent_state):
        """Test observations respect pagination limits"""

        for i in range(15):
            observation = ActionResult(thought=f"Thought {i}", action=f"action_{i}", result=f"Result {i}")
            mock_agent_state.observations.append(observation)

        observations_str = mock_agent_state.build_observations()
        observation_count = observations_str.count("Result")
        assert observation_count <= 10

    @pytest.mark.asyncio
    async def test_memory_block_token_limit_enforcement(self):
        """Test memory blocks enforce token limits for pagination"""
        from app.common.models import MemoryManagementConfig

        memory_entry = MemoryEntry(id=uuid4(), user_id=uuid4(), memory_type=MemoryType.PERSONA, content="x" * 2000, embedding=[], metadata={})

        serialized = memory_entry.serialize()

        assert "chars" in serialized["header"]
        assert "tokens" in serialized["header"]
        assert "%" in serialized["header"]

        if len(memory_entry.content) / MemoryManagementConfig.AVERAGE_TOKEN_SIZE > memory_entry.memory_type.token_limit * 0.7:
            assert "⚠️" in serialized["header"]

    @pytest.mark.asyncio
    async def test_empty_paginated_results(self, mock_agent_state):
        """Test handling of empty paginated results"""

        mock_agent_state.recall_paginated_result = None
        context = mock_agent_state.build_conversation_context()
        assert context == {}

        empty_result = PaginatedMemoryResult(results=[], page=1, total_pages=0, total_count=0, page_size=10)
        mock_agent_state.recall_paginated_result = empty_result
        context = mock_agent_state.build_conversation_context()
        assert context == {}
