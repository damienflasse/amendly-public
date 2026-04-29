"""add plan_expires_at to users

Revision ID: 0030_add_user_plan_expires_at
Revises: 0029_add_processed_stripe_events
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_add_user_plan_expires_at"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "plan_expires_at")
