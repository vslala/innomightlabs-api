from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.common.config import ServiceFactory


class UserPopulationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Middleware to populate the request state with user information based on the 'x-username' header.
        This middleware retrieves the user ID from the 'x-username' header, fetches the user from the service,
        and attaches the user object to the request state for later use in the application.
        """
        if request.method == "POST" and "/users" in request.url.path:
            return await call_next(request)
        x_username = request.headers.get("x-forwarded-user")
        user = None
        if x_username:
            service = ServiceFactory.get_user_service()
            user = await service.get_user_by_username(x_username)
        request.state.user = user
        response = await call_next(request)
        return response
