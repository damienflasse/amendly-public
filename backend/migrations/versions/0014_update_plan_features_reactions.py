"""Update plan_config features to reflect amendment reactions (sessions 53–54).

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-27 00:00:00.000000

Reason for change:
  Sessions 53–54 added member votes (support / oppose) on amendments and a
  visual sentiment summary for owners/admins — both gated to team and
  organisation plans.  The plan_config.features JSON list is the source of
  truth for the pricing cards and billing page feature lists; it must reflect
  the new capabilities so that prospective customers see the correct
  differentiator between Solo and the paid collaborative tiers.

  Changes per plan:
    - solo        : unchanged (reactions are not available on this plan)
    - team        : add "Member votes on amendments (support / oppose)"
                    add "Sentiment summary for owners & admins"
    - organisation: same additions as team
"""

from typing import Sequence, Union

import json

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Update plan_config.features for team and organisation plans to include
    the amendment reaction and sentiment summary features added in sessions 53–54.
    """
    conn = op.get_bind()

    for plan_name, features in [
        (
            "team",
            [
                "Unlimited active documents",
                "Unlimited external contributors",
                "Word + PDF export",
                "Member votes on amendments (support / oppose)",
                "Sentiment summary for owners & admins",
                "7-day free trial",
            ],
        ),
        (
            "organisation",
            [
                "Unlimited active documents",
                "Unlimited external contributors",
                "Word + PDF + CSV + JSON export",
                "Member votes on amendments (support / oppose)",
                "Sentiment summary for owners & admins",
                "7-day free trial",
            ],
        ),
    ]:
        conn.execute(
            sa.text(
                "UPDATE plan_config SET features = :features WHERE plan_name = :plan_name"
            ),
            {"features": json.dumps(features), "plan_name": plan_name},
        )


def downgrade() -> None:
    """Revert plan_config.features for team and organisation plans to the session 52 state."""
    conn = op.get_bind()

    for plan_name, features in [
        (
            "team",
            [
                "Unlimited active documents",
                "External contributors",
                "Word + PDF export",
                "7-day free trial",
            ],
        ),
        (
            "organisation",
            [
                "Unlimited active documents",
                "External contributors",
                "Word + PDF + CSV + JSON export",
                "7-day free trial",
            ],
        ),
    ]:
        conn.execute(
            sa.text(
                "UPDATE plan_config SET features = :features WHERE plan_name = :plan_name"
            ),
            {"features": json.dumps(features), "plan_name": plan_name},
        )
