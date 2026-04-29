"""Make amendments.author_id nullable to match ON DELETE SET NULL FK cascade.

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  The amendments.author_id column carries ON DELETE SET NULL on its FK to
  users.id, but was incorrectly declared NOT NULL. These two constraints are
  contradictory: if a user row were deleted at the DB level, PostgreSQL would
  attempt to set author_id to NULL and immediately fail the NOT NULL check.

  While Amendly performs soft-delete (GDPR erasure keeps the user row), the
  contradiction creates a latent integrity risk for any direct DB maintenance
  or future code path that hard-deletes a user.

  Fix: drop the NOT NULL constraint so the column can actually hold NULL when
  the FK cascade fires, matching the intent of ondelete="SET NULL".

  SQLite note: ALTER COLUMN is handled via batch mode.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop NOT NULL constraint on amendments.author_id."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("amendments", "author_id", nullable=True)
    else:
        with op.batch_alter_table("amendments") as batch_op:
            batch_op.alter_column("author_id", nullable=True, existing_type=sa.String(36))


def downgrade() -> None:
    """Restore NOT NULL constraint on amendments.author_id (best-effort)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("amendments", "author_id", nullable=False)
    else:
        with op.batch_alter_table("amendments") as batch_op:
            batch_op.alter_column("author_id", nullable=False, existing_type=sa.String(36))
