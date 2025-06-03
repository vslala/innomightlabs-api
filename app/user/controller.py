from typing import Annotated
from fastapi import APIRouter, Header
from app.common.controller import BaseController
from app.common.models import RequestHeaders
from app.user.models import UserRequest


class UserController(BaseController):
    prefix = "user"
    
    @property
    def router(self) -> APIRouter:
        
        @self.api_router.post("")
        async def create_user(request: UserRequest, headers: Annotated[RequestHeaders, Header()]):
            pass
        
        
        return self.api_router
            