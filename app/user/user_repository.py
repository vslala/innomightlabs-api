from uuid import UUID
from app.common.repositories import BaseRepository
from app.user import User as UserDomain
from app.common.exceptions import NotFoundException
from app.user.entities import UserEntity


class UserRepository(BaseRepository):
    """Repository for user-related database operations."""

    def __init__(self, session):
        super().__init__(session)

    def get_user_by_id(self, user_id: UUID) -> UserDomain:
        """Retrieve a user by their ID."""
        user = self.session.query(UserEntity).filter(UserEntity.id == user_id).first()
        if not user:
            raise NotFoundException(f"User with ID {user_id} not found.")
        return UserDomain.from_entity(user)

    def get_user_by_username(self, username: str) -> UserDomain:
        """Retrieve a user by their username."""
        user = self.session.query(UserEntity).filter(UserEntity.username == username).first()
        if not user:
            raise NotFoundException(f"User with username '{username}' not found.")
        return UserDomain.from_entity(user)

    def create_user(self, user: UserDomain) -> UserDomain:
        """Create a new user."""
        if self.session.query(UserEntity).filter(UserEntity.username == user.username).first():
            raise ValueError(f"User with username {user.username} already exists.")

        new_user = UserEntity()
        new_user.username = user.username
        self.session.add(new_user)
        self.commit()
        return UserDomain.from_entity(new_user)

    def update_user(self, user_id: UUID, user: UserDomain) -> None:
        """Update an existing user's information."""
        existing_user = self.get_user_by_id(user_id)
        existing_user.username = user.username
        self.session.commit()

    def delete_user(self, user_id: UUID) -> bool:
        """Delete a user by their ID."""
        user = self.get_user_by_id(user_id)
        if user:
            self.session.delete(user)
            self.commit()
            return True
        return False
