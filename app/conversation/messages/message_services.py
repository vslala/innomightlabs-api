from app.chatbot.chatbot_services import ChatbotService
from app.common.repositories import TransactionManager
from app.conversation.messages import Message
from app.conversation.messages.message_repositories import MessageRepository
from app.user import User


class MessageService:
    def __init__(
        self,
        transaction_manager: TransactionManager,
        message_repository: MessageRepository,
        chatbot_service: ChatbotService,
    ) -> None:
        self.repository = message_repository
        self.transaction_manager = transaction_manager
        self.chatbot_service = chatbot_service

    """
    Service class for handling message-related operations.
    This class contains methods for sending and processing messages in a conversation.
    """

    async def add_messages(self, user: User, user_message: Message, agent_response: Message) -> tuple[Message, Message]:
        """the message will be sent to the chatbot and persisted in the database."""
        if user.id is None:
            raise ValueError("User ID cannot be None when creating a message.")

        # Generate embeddings for the user message and agent response
        user_message.embedding = await self.chatbot_service.generate_embedding(user_message.content)
        agent_response.embedding = await self.chatbot_service.generate_embedding(agent_response.content)

        # Create the user and agent message in the database
        with self.transaction_manager as session:
            self.repository.create_message(session=session, message=user_message, sender_id=user.id)

            agent_response.parent_message_id = user_message.id
            self.repository.create_message(session=session, message=agent_response, sender_id=user.id)

        return (user_message, agent_response)
