"""Add onboarding_completed column to users.

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-03 00:00:00.000000

Reason for change:
  Introduces server-side tracking of the post-signup onboarding wizard
  completion state.  Previously the wizard relied on a localStorage key
  ('amendly_onboarding_v1') which was per-device and lost on new browsers.
  The new column persists the state in the database so the wizard is only
  shown once per user account, regardless of device.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add onboarding_completed boolean column (default False) to users."""
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    """Remove onboarding_completed column from users."""
    op.drop_column("users", "onboarding_completed")
