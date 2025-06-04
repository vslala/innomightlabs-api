from uuid import uuid4
from pydantic import BaseModel

from pydantic import Field


UUID_FIELD = Field(
    description="Unique Identifier of the Resource",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
)

UUID_FIELD_WITH_DEFAULT = Field(
    description="Unique Identifier of the Resource",
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    default_factory=lambda: str(uuid4()),
)


# Requests
class RequestHeaders(BaseModel):
    x_forwarded_user: str
