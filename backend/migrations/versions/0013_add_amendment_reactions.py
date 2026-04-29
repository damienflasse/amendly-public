"""Add amendment_reactions table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  Adds the `amendment_reactions` table to support member votes on amendments.
  Each member may express support (+1) or opposition (-1) on a pending amendment.
  The unique constraint on (user_id, amendment_id) ensures one reaction per user
  per amendment. Re-posting the same type cancels the reaction (toggle semantics
  handled in the service layer).
  Feature is gated to team and organisation plans.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Create enum idempotently — DO block prevents "type already exists" on retry
        # and avoids asyncpg ORM event hooks triggered by sa.Enum inside create_table.
        op.execute(sa.text("""
            DO $$ BEGIN
                CREATE TYPE reaction_type AS ENUM ('support', 'oppose');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """))
        reaction_col_type = postgresql.ENUM(name="reaction_type", create_type=False)
    else:
        reaction_col_type = sa.String(16)

    op.create_table(
        "amendment_reactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "amendment_id",
            sa.String(36),
            sa.ForeignKey("amendments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reaction_type",
            reaction_col_type,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "amendment_id", name="uq_reaction_user_amendment"),
    )
    op.create_index("ix_amendment_reactions_amendment_id", "amendment_reactions", ["amendment_id"])
    op.create_index("ix_amendment_reactions_user_id", "amendment_reactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_amendment_reactions_user_id", table_name="amendment_reactions")
    op.drop_index("ix_amendment_reactions_amendment_id", table_name="amendment_reactions")
    op.drop_table("amendment_reactions")
    op.execute("DROP TYPE IF EXISTS reaction_type")
