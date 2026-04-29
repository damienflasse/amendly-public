"""add email_notifications_enabled preference to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-22 00:00:00.000000

Reason for change: Per-user opt-out for amendment status notification emails.
  Adds a boolean column `email_notifications_enabled` (default TRUE) to the
  users table.  When FALSE, the amendment service skips sending the
  accepted/rejected notification email to that author.  This satisfies the
  legal requirement under GDPR/ePrivacy to offer an opt-out for transactional
  notification emails that are not strictly necessary to deliver the service.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email_notifications_enabled column to users (default TRUE)."""
    op.add_column(
        "users",
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment=(
                "When FALSE the user has opted out of amendment status "
                "notification emails.  All existing and new accounts default "
                "to TRUE (opted in)."
            ),
        ),
    )


def downgrade() -> None:
    """Remove email_notifications_enabled from users."""
    op.drop_column("users", "email_notifications_enabled")
