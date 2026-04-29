"""
PlanConfig model — database-driven pricing configuration for each plan tier.

Each row describes one billable plan (solo, team, organisation).
Prices, user limits, and feature lists are stored here so that the platform
administrator can modify them through the /admin/pricing UI without code changes
or redeployment.

The `features` column stores a JSON-serialised list of strings shown on the
pricing cards.  SQLAlchemy's JSON type maps to JSONB on PostgreSQL and TEXT on
SQLite (used in tests).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlanConfig(Base):
    """
    SQLAlchemy ORM model for a plan pricing configuration row.

    Attributes:
        id: Auto-incrementing integer primary key.
        plan_name: Canonical plan identifier ('solo', 'team', 'organisation').
        base_price_cents: Monthly base price in euro cents (e.g. 900 = €9.00).
        included_users: Number of seats bundled in the base price.
        extra_user_price_cents: Per-seat per-month price for additional users, in cents.
        max_active_documents: Hard cap on active documents; NULL means unlimited.
        max_external_contributors: Hard cap on distinct external contributors per
            document; NULL means unlimited.
        stripe_price_id: Stripe Price ID for monthly billing (empty = inline price_data).
        stripe_price_id_annual: Stripe Price ID for annual billing (empty = not configured).
        features: JSON list of human-readable feature strings for the pricing card.
        is_active: When False this plan is hidden from the public /api/plans endpoint.
        updated_at: Timestamp of the last admin modification.
    """

    __tablename__ = "plan_config"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    plan_name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    base_price_cents: Mapped[int] = mapped_column(Integer(), nullable=False)
    included_users: Mapped[int] = mapped_column(Integer(), nullable=False)
    extra_user_price_cents: Mapped[int] = mapped_column(Integer(), nullable=False)
    max_active_documents: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    max_external_contributors: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    stripe_price_id: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    stripe_price_id_annual: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=""
    )
    features: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<PlanConfig plan_name={self.plan_name!r} "
            f"base_price_cents={self.base_price_cents}>"
        )
