"""Add amendment_commented value to activity_action enum.

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-30 00:00:00.000000

Reason for change:
  Session 83 introduces comment-notification emails: when a member posts a
  comment on an amendment, the amendment author receives an email and the
  event is recorded in the activity log.  The new 'amendment_commented'
  value is added to the activity_action PostgreSQL enum to support this.

  On SQLite (test environment) the column is a plain VARCHAR so no ALTER
  is needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Extend the activity_action enum with the 'amendment_commented' value."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # ALTER TYPE … ADD VALUE is idempotent in PG 9.6+ when using IF NOT EXISTS
        op.execute(
            sa.text("ALTER TYPE activity_action ADD VALUE IF NOT EXISTS 'amendment_commented'")
        )
    # SQLite stores enum as VARCHAR — no schema change required.


def downgrade() -> None:
    """PostgreSQL does not support removing enum values; downgrade is a no-op.

    To fully revert, recreate the enum without 'amendment_commented' and
    migrate the column — only necessary if rows with this value exist.
    """
