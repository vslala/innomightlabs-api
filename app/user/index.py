from pydantic import BaseModel


class User(BaseModel):
    """Represents a user in the system."""
    
    def __init__(self, username: str):
        self.username = username