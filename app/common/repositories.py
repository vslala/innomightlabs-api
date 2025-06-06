from sqlalchemy.orm import Session


class BaseRepository:
    """Base class for all repositories."""

    def __init__(self, session: Session):
        """
        Every derived “Repository” gets a SQLAlchemy Session injected.
        """
        self.session = session

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()


class TransactionManager(BaseRepository):
    """
    Transaction manager for handling transactions in the application.
    This class provides methods to commit, rollback, and close transactions.
    """

    def __init__(self, session: Session):
        super().__init__(session)

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
