"""Set the live Stripe monthly price ID for the solo plan.

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  Session 55 initially backfilled only team and organisation Stripe price IDs.
  The production Stripe account also has a live recurring monthly price for the
  solo plan, and plan_config should reference it explicitly rather than rely on
  deprecated fallback behaviour.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOLO_PRICE_ID = "price_SOLO_MONTHLY_PLACEHOLDER"


def upgrade() -> None:
    """Backfill the live Stripe monthly price ID for the solo plan."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET stripe_price_id = :price_id
            WHERE plan_name = 'solo'
            """
        ),
        {"price_id": SOLO_PRICE_ID},
    )


def downgrade() -> None:
    """Clear the Stripe monthly price ID for the solo plan."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET stripe_price_id = ''
            WHERE plan_name = 'solo'
            """
        )
    )
