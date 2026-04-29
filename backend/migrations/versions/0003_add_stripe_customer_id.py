"""add stripe_customer_id to organisations

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-21 00:00:00.000000

Reason for change: Adds the stripe_customer_id column to the organisations table
to store the Stripe Customer object ID created during the first Checkout session.
This column is used by the Stripe webhook handler to identify which organisation
a billing event belongs to (checkout.session.completed, customer.subscription.deleted).
Nullable because free-tier orgs that have never started a checkout have no customer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add stripe_customer_id to organisations."""
    op.add_column(
        "organisations",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_organisations_stripe_customer_id",
        "organisations",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_organisations_stripe_customer_id",
        "organisations",
        ["stripe_customer_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove stripe_customer_id from organisations."""
    op.drop_index("ix_organisations_stripe_customer_id", table_name="organisations")
    op.drop_constraint(
        "uq_organisations_stripe_customer_id",
        "organisations",
        type_="unique",
    )
    op.drop_column("organisations", "stripe_customer_id")
