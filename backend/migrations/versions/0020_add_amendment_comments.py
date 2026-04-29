"""Add amendment_comments table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-30 00:00:00.000000

Reason for change:
  Users have requested a way to discuss individual amendments without having
  to submit a new general_comment amendment. The new amendment_comments table
  provides a lightweight threaded discussion on each amendment card.

  Any member may post a comment; the author or an org owner/admin may delete it.
  Comments are hard-deleted (no soft-delete) as they carry no lifecycle state.
  Cascades: deleting an amendment deletes its comments; deleting a user sets
  author_id to NULL so the comment body is preserved.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the amendment_comments table."""
    op.create_table(
        "amendment_comments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("amendment_id", sa.String(36), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["amendment_id"],
            ["amendments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_amendment_comments_amendment_id", "amendment_comments", ["amendment_id"])
    op.create_index("ix_amendment_comments_author_id", "amendment_comments", ["author_id"])


def downgrade() -> None:
    """Drop the amendment_comments table."""
    op.drop_index("ix_amendment_comments_author_id", table_name="amendment_comments")
    op.drop_index("ix_amendment_comments_amendment_id", table_name="amendment_comments")
    op.drop_table("amendment_comments")
