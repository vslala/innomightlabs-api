from app.common.controller import BaseController
from app.conversation.messages.message_controller import MessageController


def get_controllers() -> list[type[BaseController]]:
    from app.conversation.conversation_controller import ConversationController
    from app.user.user_controller import UserController
    from app.chatbot.chatbot_controller import AgentController

    return [AgentController, UserController, ConversationController, MessageController]
