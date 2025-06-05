from fastapi import APIRouter, Depends
from app.common.config import ServiceFactory
from app.common.controller import BaseController
from app.user.models import UserCreateRequest, UserResponse
from app.user.services import UserService


class UserController(BaseController):
    prefix = "user"

    @property
    def router(self) -> APIRouter:
        @self.api_router.post("")
        async def create_user(request: UserCreateRequest, user_service: UserService = Depends(ServiceFactory.get_user_service)) -> UserResponse:
            user = await user_service.add_user(request)
            return UserResponse(**user.model_dump())

        return self.api_router
