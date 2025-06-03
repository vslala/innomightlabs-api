"""create pgvector extension

Revision ID: e0411fc4eebd
Revises:
Create Date: 2025-06-03 16:34:23.802055

"""

import os
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "001_create_pgvector_extension"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__),  # current directory of this file
        os.pardir,
        "raw_sql",
        "001_create_pgvector_extension.sql",
    )
    with open(sql_path, "r") as file:
        op.execute(file.read())


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS vector;")
