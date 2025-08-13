from app.common.controller import BaseController


def get_controllers() -> list[type[BaseController]]:
    from app.user.user_controller import UserController
    from app.chatbot.chatbot_controller import ChatbotController

    return [ChatbotController, UserController]
