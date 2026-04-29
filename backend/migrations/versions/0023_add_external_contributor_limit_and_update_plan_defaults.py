"""Add external contributor limits and refresh plan defaults.

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-28 00:00:00.000000

Reason for change:
  Team now has a configurable cap on active documents (20 by default) and a
  configurable cap on distinct external contributors (30 by default). The
  Organisation plan keeps unlimited external contributors and becomes the only
  tier advertising member votes / sentiment reactions. Export promises are
  also aligned with the product by adding CSV and JSON to the Organisation
  plan's feature list.
"""

from typing import Sequence, Union

import json

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the contributor cap column and update the default plan rows."""
    op.add_column(
        "plan_config",
        sa.Column(
            "max_external_contributors",
            sa.Integer(),
            nullable=True,
            comment="Hard cap on distinct external contributors per document; NULL means unlimited.",
        ),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = 3,
                max_external_contributors = 0,
                features = :features
            WHERE plan_name = 'solo'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Up to 3 active documents",
                    "No external contributors",
                    "Word (DOCX) export",
                    "7-day free trial",
                ]
            )
        },
    )
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = 20,
                max_external_contributors = 30,
                features = :features
            WHERE plan_name = 'team'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Up to 20 active documents",
                    "Up to 30 external contributors",
                    "Word + PDF export",
                    "7-day free trial",
                ]
            )
        },
    )
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = NULL,
                max_external_contributors = NULL,
                features = :features
            WHERE plan_name = 'organisation'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Unlimited active documents",
                    "Unlimited external contributors",
                    "Word + PDF + TXT + CSV + JSON export",
                    "Member votes on amendments (support / oppose)",
                    "Sentiment summary for owners & admins",
                    "7-day free trial",
                ]
            )
        },
    )


def downgrade() -> None:
    """Restore the previous plan defaults and drop the contributor cap column."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = 3,
                features = :features
            WHERE plan_name = 'solo'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Up to 3 active documents",
                    "Word (DOCX) export",
                    "7-day free trial",
                ]
            )
        },
    )
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = NULL,
                features = :features
            WHERE plan_name = 'team'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Unlimited active documents",
                    "Unlimited external contributors",
                    "Word + PDF export",
                    "Member votes on amendments (support / oppose)",
                    "Sentiment summary for owners & admins",
                    "7-day free trial",
                ]
            )
        },
    )
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_active_documents = NULL,
                features = :features
            WHERE plan_name = 'organisation'
            """
        ),
        {
            "features": json.dumps(
                [
                    "Unlimited active documents",
                    "Unlimited external contributors",
                    "Word + PDF + CSV + JSON export",
                    "Member votes on amendments (support / oppose)",
                    "Sentiment summary for owners & admins",
                    "7-day free trial",
                ]
            )
        },
    )
    conn.execute(
        sa.text(
            """
            UPDATE plan_config
            SET max_external_contributors = NULL
            """
        )
    )
    op.drop_column("plan_config", "max_external_contributors")
