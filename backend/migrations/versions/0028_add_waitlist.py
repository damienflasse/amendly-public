"""Add waitlist_entries table for pre-launch email capture.

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-06 00:00:00.000000

Reason for change:
  Visitors can join a waitlist on the landing page before the public launch.
  Entries are captured in a dedicated table, kept separate from prospects so
  that the sales pipeline remains clean.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create waitlist_entries table."""
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_waitlist_entries_email",
        "waitlist_entries",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    """Drop waitlist_entries table."""
    op.drop_index("ix_waitlist_entries_email", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
