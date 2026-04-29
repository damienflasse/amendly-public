"""add is_superuser to users and create plan_config table

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-22 00:00:00.000000

Reason for change: Introduces a platform-level superuser flag on users (distinct
from org-scoped owner/admin/member roles) and a plan_config table that becomes the
single source of truth for all pricing data.  Seeds the three paid tiers — Solo,
Team, Organisation — so that the admin pricing interface has data on first boot.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Add is_superuser boolean column to users (default FALSE).
    2. Create plan_config table with pricing data for each plan tier.
    3. Seed the three initial plans: solo, team, organisation.
    """
    # -------------------------------------------------------------------------
    # Add is_superuser to users
    # -------------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "Platform-level superuser flag.  When TRUE the user can access "
                "/api/admin/* endpoints.  Distinct from org-level roles.  "
                "Set via SUPERUSER_EMAIL env var on startup."
            ),
        ),
    )

    # -------------------------------------------------------------------------
    # Create plan_config table
    # -------------------------------------------------------------------------
    op.create_table(
        "plan_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "plan_name",
            sa.String(20),
            nullable=False,
            comment="Canonical plan identifier: 'solo', 'team', or 'organisation'",
        ),
        sa.Column(
            "base_price_cents",
            sa.Integer(),
            nullable=False,
            comment="Monthly base price in euro cents (e.g. 900 = €9.00)",
        ),
        sa.Column(
            "included_users",
            sa.Integer(),
            nullable=False,
            comment="Number of seats included in the base price",
        ),
        sa.Column(
            "extra_user_price_cents",
            sa.Integer(),
            nullable=False,
            comment="Price per additional seat per month, in euro cents",
        ),
        sa.Column(
            "max_active_documents",
            sa.Integer(),
            nullable=True,
            comment="Maximum number of active documents; NULL means unlimited",
        ),
        sa.Column(
            "stripe_price_id",
            sa.String(255),
            nullable=False,
            server_default="",
            comment="Stripe Price ID for monthly billing (empty = use inline price_data)",
        ),
        sa.Column(
            "stripe_price_id_annual",
            sa.String(255),
            nullable=False,
            server_default="",
            comment="Stripe Price ID for annual billing (empty = not configured)",
        ),
        sa.Column(
            "features",
            sa.Text(),
            nullable=False,
            server_default="[]",
            comment="JSON array of feature strings displayed on pricing cards",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="When FALSE this plan is hidden from the public /api/plans endpoint",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Timestamp of the last admin update",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_name"),
    )

    # -------------------------------------------------------------------------
    # Seed initial plan data
    # -------------------------------------------------------------------------
    op.bulk_insert(
        sa.table(
            "plan_config",
            sa.column("plan_name", sa.String),
            sa.column("base_price_cents", sa.Integer),
            sa.column("included_users", sa.Integer),
            sa.column("extra_user_price_cents", sa.Integer),
            sa.column("max_active_documents", sa.Integer),
            sa.column("stripe_price_id", sa.String),
            sa.column("stripe_price_id_annual", sa.String),
            sa.column("features", sa.Text),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {
                "plan_name": "solo",
                "base_price_cents": 900,
                "included_users": 1,
                "extra_user_price_cents": 0,
                "max_active_documents": 3,
                "stripe_price_id": "",
                "stripe_price_id_annual": "",
                "features": '["Up to 3 active documents", "Word (DOCX) export", "7-day free trial"]',
                "is_active": True,
            },
            {
                "plan_name": "team",
                "base_price_cents": 2900,
                "included_users": 3,
                "extra_user_price_cents": 800,
                "max_active_documents": None,
                "stripe_price_id": "",  # Set via STRIPE_PRICE_ID env var or admin panel
                "stripe_price_id_annual": "",  # Set via admin panel
                "features": '["Unlimited active documents", "External contributors", "Word + PDF export", "7-day free trial"]',
                "is_active": True,
            },
            {
                "plan_name": "organisation",
                "base_price_cents": 9900,
                "included_users": 10,
                "extra_user_price_cents": 600,
                "max_active_documents": None,
                "stripe_price_id": "",  # Set via admin panel
                "stripe_price_id_annual": "",  # Set via admin panel
                "features": '["Unlimited active documents", "External contributors", "Word + PDF + CSV + JSON export", "7-day free trial"]',
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    """Remove plan_config table and is_superuser column."""
    op.drop_table("plan_config")
    op.drop_column("users", "is_superuser")
