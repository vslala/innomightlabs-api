from app.common.repositories import BaseRepository
from app.user.index import User as UserDomain
from app.common.exceptions import NotFoundException
from app.user.repositories.entities import User


class UserRepository(BaseRepository):
    """Repository for user-related database operations."""

    def __init__(self, session):
        super().__init__(session)

    def get_user_by_id(self, user_id: int) -> User:
        """Retrieve a user by their ID."""
        user = self.session.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found.")
        return user

    def create_user(self, user: UserDomain) -> User:
        """Create a new user."""
        new_user = User()
        new_user.username = user.username
        self.session.add(new_user)
        self.commit()
        return new_user

    def update_user(self, user_id: int, user: UserDomain) -> None:
        """Update an existing user's information."""
        existing_user = self.get_user_by_id(user_id)
        existing_user.username = user.username
        self.session.commit()
        

    def delete_user(self, user_id: int):
        """Delete a user by their ID."""
        user = self.get_user_by_id(user_id)
        if user:
            self.session.delete(user)
            self.commit()
            return True
        return False