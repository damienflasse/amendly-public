"""Set the live Stripe annual price ID for the solo plan.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  The solo plan also has a live annual Stripe recurring price. Existing
  environments need that annual price ID backfilled into plan_config so the
  annual checkout path uses the canonical Stripe price rather than inline
  fallback pricing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOLO_ANNUAL_PRICE_ID = ""  # REPLACE: your solo annual Stripe Price ID (e.g. price_xxx)


def upgrade() -> None:
    """Backfill the live Stripe annual price ID for the solo plan."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET stripe_price_id_annual = :price_id
            WHERE plan_name = 'solo'
            """
        ),
        {"price_id": SOLO_ANNUAL_PRICE_ID},
    )


def downgrade() -> None:
    """Clear the Stripe annual price ID for the solo plan."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET stripe_price_id_annual = ''
            WHERE plan_name = 'solo'
            """
        )
    )
