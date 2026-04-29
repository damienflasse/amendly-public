"""add user deletion fields for GDPR right to erasure

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-22 00:00:00.000000

Reason for change: GDPR Article 17 (right to erasure).  Adds two nullable
columns to the users table:
  - deleted_at  — timestamp set when the user requests account deletion.
    A non-NULL value means the account is soft-deleted / anonymised.
  - is_deleted  — boolean flag for fast filtering without parsing a timestamp.

Email and name are anonymised in-place by the DELETE /api/auth/me endpoint
(they are overwritten with placeholder strings).  The columns are nullable
so that existing rows are unaffected by the migration and no backfill is
needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at and is_deleted columns to the users table."""
    op.add_column(
        "users",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when the user requested account deletion (GDPR erasure).",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True when the account has been anonymised via GDPR erasure.",
        ),
    )
    # Index for fast exclusion of deleted accounts in auth lookups
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])


def downgrade() -> None:
    """Remove the deletion columns from the users table."""
    op.drop_index("ix_users_is_deleted", table_name="users")
    op.drop_column("users", "is_deleted")
    op.drop_column("users", "deleted_at")
