"""Add contributor link expiry timestamp to documents.

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-05 00:00:00.000000

Reason for change:
  Public contributor links now have a business expiry window. The token itself
  remains nullable for revocation, while expiry is tracked separately so the
  API can distinguish active, expired, and revoked links.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contributor_token_expires_at to documents."""
    op.add_column(
        "documents",
        sa.Column(
            "contributor_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove contributor_token_expires_at from documents."""
    op.drop_column("documents", "contributor_token_expires_at")
