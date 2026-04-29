"""add_processed_stripe_events

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-16

Adds a table to record Stripe event IDs that have already been processed,
preventing duplicate side-effects from replayed or out-of-order webhooks.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_stripe_events",
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_stripe_events")
