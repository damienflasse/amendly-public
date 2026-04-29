"""Add notifications_last_read_at to users.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  Adds `notifications_last_read_at` (nullable DateTime) to the users table.
  This timestamp marks the last moment the user acknowledged their in-app
  notification feed. Any activity_log entry created after this timestamp
  (in orgs where the user is a member on a team+ plan) is counted as unread.
  NULL means the user has never opened the notification center — all entries
  are treated as unread.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notifications_last_read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_last_read_at")
