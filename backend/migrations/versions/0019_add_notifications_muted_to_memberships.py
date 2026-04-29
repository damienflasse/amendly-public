"""Add notifications_muted boolean to memberships table.

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-28 00:00:00.000000

Reason for change:
  Users have requested per-organisation notification control. The global
  email_notifications_enabled flag on the users table already lets a user
  opt out of all amendment-status emails. This new column allows a finer
  granularity: a user can silence notifications for a single org (e.g. a
  low-priority org they belong to) while keeping them active for others.

  notifications_muted defaults to FALSE so all existing memberships continue
  to receive notifications as before — no behavioural change for current users.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notifications_muted column to memberships (default FALSE, not null)."""
    op.add_column(
        "memberships",
        sa.Column(
            "notifications_muted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Remove notifications_muted column from memberships."""
    op.drop_column("memberships", "notifications_muted")
