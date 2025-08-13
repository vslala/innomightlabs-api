import json
import asyncio
from abc import ABC, abstractmethod
from app.chatbot import BaseChatbot
from app.chatbot.chatbot_models import SingleMessage
from app.chatbot.conversation.conversation_repositories import ConversationRepository
from app.chatbot.messages import Message
from app.chatbot.messages.message_repositories import MessageRepository
from app.common.models import MemoryManagementConfig, Role
from app.common.vector_embedders import BaseVectorEmbedder
from app.user import User
from uuid import UUID
from app.common.utils import extract_tag_content
from loguru import logger


class ConversationManager(ABC):
    def __init__(
        self,
        user: User,
        current_user_message: str,
        conversation_id: UUID,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        embedder: BaseVectorEmbedder,
        chatbot: BaseChatbot,
    ):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.user = user
        self.current_user_message = current_user_message
        self.conversation_id = conversation_id
        self.embedder = embedder
        self.chatbot = chatbot

    @abstractmethod
    async def handle_messages(self) -> None:
        pass

    @abstractmethod
    async def get_messages(self) -> list[Message]:
        """
        Get all messages from the conversation
        """
        raise NotImplementedError

    @abstractmethod
    async def append_message(self, message: SingleMessage) -> None:
        """
        Add a message to the conversation
        """
        raise NotImplementedError

    async def dump_messages(self) -> list[str]:
        """
        Dump all messages from the conversation as JSON strings
        """
        messages = await self.get_messages()
        return [m.model_dump_json() for m in messages]

    @abstractmethod
    async def handle_final_response(self) -> None:
        raise NotImplementedError


class SlidingWindowConversationManager(ConversationManager):
    def __init__(
        self,
        user: User,
        current_user_message: str,
        conversation_id: UUID,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        embedder: BaseVectorEmbedder,
        chatbot: BaseChatbot,
        window_size: int = MemoryManagementConfig.CONVERSATION_PAGE_SIZE,
    ):
        super().__init__(
            user=user,
            current_user_message=current_user_message,
            conversation_id=conversation_id,
            conversation_repository=conversation_repository,
            message_repository=message_repository,
            embedder=embedder,
            chatbot=chatbot,
        )
        self.window_size = window_size
        self.session_messages: list[Message] = []

    async def handle_messages(self) -> None:
        """
        This method will be called after the LLM response to handle the messages

        Args:
            messages (list[Message]): _description_
        """
        if len(self.session_messages) > self.window_size:
            self.stored_messages = self.session_messages[-self.window_size :]

    async def get_messages(self) -> list[Message]:
        """
        Get all messages from the conversation
        """
        if not self.session_messages:
            result = await self.message_repository.fetch_all_paginated_by_user_id(user_id=self.user.id)
            self.session_messages = result.results

        return sorted(self.session_messages, key=lambda x: x.created_at)

    async def append_message(self, message: SingleMessage) -> None:
        self.session_messages.append(
            Message(content=message.message, role=message.role, conversation_id=self.conversation_id, embedding=self.embedder.embed_single_text(message.message))
        )

    async def _update_conversation_title_and_summary(self) -> None:
        conversation = self.conversation_repository.find_conversation_by_id(conversation_id=self.conversation_id)
        if not conversation.summary or conversation.title == "New Conversation":
            logger.info("Updating conversation title and summary")
            agent_response = self.chatbot.get_text_response(
                prompt=f"""
            Given the opening conversation between the chatbot and the user, provide the following:
            1. Title: concise title less than 50 characters to be displayed on the conversation
            2. Summary: concise summary of the conversation in markdown format in bullet points
            
            Output Format:
            
            <title>...the title of the conversation...</title>
            <summary>...markdown summary of the given conversation</summary>
            
            Note: strictly provide the title and summary within the provided tags
            
            Conversation History:
            {json.dumps([SingleMessage.from_message(m).model_dump_json() for m in self.session_messages])}
            """
            )
            title = extract_tag_content(agent_response, "title")[0]
            summary = extract_tag_content(agent_response, "summary")[0]
            conversation.title = title
            conversation.summary = summary
            conversation.summary_embeddings = self.embedder.embed_single_text(summary)
            self.conversation_repository.update_conversation(domain=conversation)

    async def handle_final_response(self) -> None:
        """
        This method will be called when the final response is received
        """

        final_response = self.session_messages[-1].content

        self.message_repository.batch_add_messages(
            user_id=self.user.id,
            messages=[
                Message(
                    content=self.current_user_message, role=Role.USER, conversation_id=self.conversation_id, embedding=self.embedder.embed_single_text(self.current_user_message)
                ),
                Message(content=final_response, role=Role.ASSISTANT, conversation_id=self.conversation_id, embedding=self.embedder.embed_single_text(final_response)),
            ],
        )

        asyncio.create_task(self._update_conversation_title_and_summary())
