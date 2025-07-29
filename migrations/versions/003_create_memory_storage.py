"""create memory storage

Revision ID: 003
Revises: 002
Create Date: 2025-07-28 20:02:09.320812

"""

import os
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    sql_path = os.path.join(
        os.path.dirname(__file__),  # current directory of this file
        os.pardir,
        "raw_sql",
        "003_create_memory_storage.sql",
    )
    with open(sql_path, "r") as file:
        op.execute(file.read())


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS memory_entries CASCADE;")
    op.execute("DROP TABLE IF EXISTS memory_audit_log CASCADE;")
