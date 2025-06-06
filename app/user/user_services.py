from uuid import UUID
from app.user import User
from app.user.user_models import UserCreateRequest
from app.user.user_repository import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def get_user(self, user_id: UUID) -> User:
        return self.user_repository.get_user_by_id(user_id)

    async def get_user_by_username(self, username: str) -> User:
        return self.user_repository.get_user_by_username(username)

    async def add_user(self, userRequest: UserCreateRequest) -> User:
        user = self.user_repository.create_user(User(username=userRequest.username))
        return user
