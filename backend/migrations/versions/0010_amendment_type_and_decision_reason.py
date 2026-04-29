"""Add amendment_type enum + decision_reason; make original/proposed text nullable.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-25 00:00:00.000000

Reason for change:
  1. amendment_type — amendments are not always text substitutions; sometimes they
     are general comments on a section or document. A new enum column distinguishes
     between 'text_change' (the original behaviour) and 'general_comment' (free-form
     comment with no diff). Existing rows are back-filled to 'text_change'.

  2. original_text / proposed_text become nullable so that 'general_comment'
     amendments can be stored without dummy placeholder values.

  3. decision_reason — owners and admins can now supply a written explanation when
     accepting or rejecting an amendment.  This field is nullable (no reason required).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Create amendment_type enum (PostgreSQL) or a plain VARCHAR (SQLite).
    2. Add amendment_type column — NOT NULL, default 'text_change'.
    3. Make original_text and proposed_text nullable.
    4. Add decision_reason column — nullable Text.
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        # Create enum idempotently (DO block avoids "type already exists" on retry)
        op.execute(sa.text("""
            DO $$ BEGIN
                CREATE TYPE amendment_type AS ENUM ('text_change', 'general_comment');
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """))
        # Use create_type=False — type already created above; prevents asyncpg event hook
        # from attempting a second CREATE TYPE during column addition.
        op.add_column(
            "amendments",
            sa.Column(
                "amendment_type",
                postgresql.ENUM("text_change", "general_comment", name="amendment_type", create_type=False),
                nullable=False,
                server_default="text_change",
            ),
        )
    else:
        # SQLite — use a plain VARCHAR with a CHECK constraint
        op.add_column(
            "amendments",
            sa.Column(
                "amendment_type",
                sa.String(32),
                nullable=False,
                server_default="text_change",
            ),
        )

    # Make original_text and proposed_text nullable
    if is_pg:
        op.alter_column("amendments", "original_text", nullable=True)
        op.alter_column("amendments", "proposed_text", nullable=True)
    else:
        # SQLite does not support ALTER COLUMN — recreate via batch mode
        with op.batch_alter_table("amendments") as batch_op:
            batch_op.alter_column("original_text", nullable=True, existing_type=sa.Text())
            batch_op.alter_column("proposed_text", nullable=True, existing_type=sa.Text())

    # Add decision_reason column
    op.add_column(
        "amendments",
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """
    Reverse the migration:
    1. Drop decision_reason column.
    2. Restore NOT NULL on original_text and proposed_text.
    3. Drop amendment_type column and enum type.
    """
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_column("amendments", "decision_reason")

    if is_pg:
        op.alter_column("amendments", "original_text", nullable=False)
        op.alter_column("amendments", "proposed_text", nullable=False)
        op.drop_column("amendments", "amendment_type")
        op.execute("DROP TYPE amendment_type")
    else:
        with op.batch_alter_table("amendments") as batch_op:
            batch_op.alter_column("original_text", nullable=False, existing_type=sa.Text())
            batch_op.alter_column("proposed_text", nullable=False, existing_type=sa.Text())
            batch_op.drop_column("amendment_type")
