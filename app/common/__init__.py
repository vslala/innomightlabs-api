from app.common.controller import BaseController


def get_controllers() -> list[type[BaseController]]:
    from app.conversation.controller import ConversationController
    from app.user.controller import UserController
    from app.workflows.chatbot_controller import AgentController

    return [AgentController, UserController, ConversationController]
