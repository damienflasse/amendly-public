"""Add contributor public link columns to documents and amendments.

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-30 00:00:00.000000

Reason for change:
  Session 86 introduces the contributor public link feature. Document owners can
  generate a shareable token that lets unauthenticated external contributors
  (e.g. federation members, NGO delegates) submit amendments without being org
  members.

  Documents:
    - contributor_token:            VARCHAR(64) nullable, unique — 32-byte hex
      secret that identifies the contribution page.
    - contributor_token_created_at: TIMESTAMPTZ nullable — when the token was
      last generated (used for display and for revocation audit trail).

  Amendments:
    - contributor_name:  VARCHAR(100) nullable — display name provided by the
      anonymous contributor at submission time.
    - contributor_email: VARCHAR(254) nullable — optional contact email for
      the anonymous contributor.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contributor_token columns to documents and contributor columns to amendments."""
    # --- documents ---
    op.add_column(
        "documents",
        sa.Column("contributor_token", sa.String(64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "contributor_token_created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Unique index on contributor_token so lookups are O(1) and duplicates are
    # prevented at the database level.
    op.create_index(
        "ix_documents_contributor_token",
        "documents",
        ["contributor_token"],
        unique=True,
    )

    # --- amendments ---
    op.add_column(
        "amendments",
        sa.Column("contributor_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "amendments",
        sa.Column("contributor_email", sa.String(254), nullable=True),
    )


def downgrade() -> None:
    """Remove contributor columns from documents and amendments."""
    op.drop_index("ix_documents_contributor_token", table_name="documents")
    op.drop_column("documents", "contributor_token_created_at")
    op.drop_column("documents", "contributor_token")
    op.drop_column("amendments", "contributor_email")
    op.drop_column("amendments", "contributor_name")
