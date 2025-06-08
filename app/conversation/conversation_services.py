from uuid import UUID
from app.chatbot.chatbot_models import AgentMessage
from app.chatbot.chatbot_services import ChatbotService
from app.conversation import Conversation
from app.conversation.conversation_models import ConversationRepositoryDTO
from app.conversation.conversation_repositories import ConversationRepository
from app.conversation.messages import Message
from app.user import User


class ConversationService:
    """
    Service class for managing conversation-related operations.
    This class handles the business logic for starting and managing conversations.
    """

    def __init__(self, conversation_repository: ConversationRepository, chatbot_service: ChatbotService):
        self.repository = conversation_repository
        self.chatbot_service = chatbot_service

    async def start_new_conversation(self, user: User) -> Conversation:
        """
        Starts a new conversation for the given user.
        """
        conversation = self.repository.create_conversation(user)
        return conversation

    async def get_all_conversations(self, user: User) -> list[Conversation]:
        conversations = self.repository.fetch_all_conversations_by_user(user=user)
        return conversations

    async def summarize(self, conversation_id: UUID, user: User, user_message: Message, agent_response: Message) -> Conversation:
        conversation = self.repository.find_conversation_by_id(conversation_id=conversation_id)
        conversation_summary = await self.chatbot_service.summarize_with_title(
            past_summary=conversation.summary,
            user_message=AgentMessage(message=user_message.content, role=user_message.role, timestamp=user_message.created_at),
            agent_response=AgentMessage(message=agent_response.content, role=agent_response.role, timestamp=agent_response.created_at),
        )
        summary_embedding = await self.chatbot_service.generate_embedding(conversation_summary.summary)
        conversation.title = conversation_summary.title
        conversation.summary = conversation_summary.summary

        conversation_dto = conversation.model_dump()
        conversation_dto["summary_embedding"] = summary_embedding
        self.repository.update_conversation(ConversationRepositoryDTO(**conversation_dto))

        return conversation
