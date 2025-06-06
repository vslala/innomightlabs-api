from app.common.controller import BaseController


def get_controllers() -> list[type[BaseController]]:
    from app.conversation.conversation_controller import ConversationController
    from app.user.user_controller import UserController
    from app.workflows.chatbot_controller import AgentController

    return [AgentController, UserController, ConversationController]
