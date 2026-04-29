"""add activity_log table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-22 00:00:00.000000

Reason for change: Introduces a simple append-only activity log that records
the most significant events in an organisation (document created, amendment
submitted/accepted/rejected/withdrawn, document status changed).  The feed is
read by the new GET /api/organisations/{slug}/activity endpoint and rendered in
the OrgDetail page.  The activity_action PostgreSQL enum is created during
upgrade and removed on downgrade.  SQLite (used in tests) does not support
CREATE TYPE so the enum is handled natively as a VARCHAR column there.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values (must match ActivityAction in app/models/activity_log.py)
_ACTIVITY_ACTIONS = [
    "document_created",
    "amendment_submitted",
    "amendment_accepted",
    "amendment_rejected",
    "amendment_withdrawn",
    "status_changed",
]


def upgrade() -> None:
    """Create the activity_log table and (on PostgreSQL) the activity_action enum."""
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Create the enum type idempotently via PL/pgSQL to avoid asyncpg ORM event hooks.
        op.execute(sa.text("""
            DO $$ BEGIN
                CREATE TYPE activity_action AS ENUM ({values});
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """.format(values=", ".join(f"'{v}'" for v in _ACTIVITY_ACTIONS))))
        # Use postgresql.ENUM to bypass the sa.Enum ORM event hook in create_table.
        action_col_type = postgresql.ENUM(name="activity_action", create_type=False)
    else:
        # SQLite: store as plain VARCHAR (tests pass without a native enum type)
        action_col_type = sa.String(64)

    op.create_table(
        "activity_log",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "doc_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "amendment_id",
            sa.String(36),
            sa.ForeignKey("amendments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", action_col_type, nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            index=True,
        ),
    )


def downgrade() -> None:
    """Drop the activity_log table and (on PostgreSQL) the activity_action enum."""
    op.drop_table("activity_log")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS activity_action")
