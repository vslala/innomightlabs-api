"""create initial table + conversation module

Revision ID: 002
Revises: 001_create_pgvector_extension
Create Date: 2025-06-03 17:42:45.971949

"""

import os
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001_create_pgvector_extension"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__),  # current directory of this file
        os.pardir,
        "raw_sql",
        "002_create_initial_table_conversation_module.sql",
    )
    with open(sql_path, "r") as file:
        op.execute(file.read())


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE;")
    op.execute("DROP TABLE IF EXISTS messages CASCADE;")
