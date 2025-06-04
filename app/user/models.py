from datetime import datetime
from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="The username of the user")


class UserResponse(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="The username of the user")
    created_at: datetime
    updated_at: datetime
