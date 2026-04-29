"""Backfill Stripe price IDs for team and organisation plans.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  Stripe recurring prices for the team and organisation plans are now live.
  Existing environments already migrated before session 55 still have empty
  stripe_price_id fields in plan_config, which makes billing fall back to
  inline price_data. This migration updates those plan rows to the canonical
  live Stripe price IDs for both monthly and annual billing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set Stripe monthly and annual price IDs for team and organisation."""
    conn = op.get_bind()

    # Replace these placeholder values with your own Stripe Price IDs.
    # Create recurring prices in your Stripe dashboard and paste the IDs here.
    updates = [
        (
            "team",
            "",  # REPLACE: your team monthly Stripe Price ID (e.g. price_xxx)
            "",  # REPLACE: your team annual Stripe Price ID
        ),
        (
            "organisation",
            "",  # REPLACE: your organisation monthly Stripe Price ID
            "",  # REPLACE: your organisation annual Stripe Price ID
        ),
    ]

    for plan_name, monthly_id, annual_id in updates:
        conn.execute(
            sa.text(
                """
                UPDATE plan_config
                SET stripe_price_id = :monthly_id,
                    stripe_price_id_annual = :annual_id
                WHERE plan_name = :plan_name
                """
            ),
            {
                "plan_name": plan_name,
                "monthly_id": monthly_id,
                "annual_id": annual_id,
            },
        )


def downgrade() -> None:
    """Clear Stripe price IDs for team and organisation."""
    conn = op.get_bind()

    for plan_name in ("team", "organisation"):
        conn.execute(
            sa.text(
                """
                UPDATE plan_config
                SET stripe_price_id = '',
                    stripe_price_id_annual = ''
                WHERE plan_name = :plan_name
                """
            ),
            {"plan_name": plan_name},
        )
