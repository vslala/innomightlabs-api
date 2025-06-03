from app.common.controller import BaseController
from app.user.controller import UserController
from app.workflows.chatbot_controller import AgentController


ALL_CONTROLLERS: list[type[BaseController]] = [
    AgentController,
    UserController,
]