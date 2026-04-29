"""
Organisation model — a workspace shared among multiple users (members).

An organisation is the top-level billing and access-control boundary.
Every document belongs to exactly one organisation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrgPlan(str, enum.Enum):
    """Billing plan at the organisation level."""

    solo = "solo"
    team = "team"
    organisation = "organisation"


class Organisation(Base):
    """
    SQLAlchemy ORM model for an organisation (team workspace).

    Attributes:
        id: UUID primary key.
        name: Human-readable display name (e.g. "ACME Federation").
        slug: URL-safe unique identifier used in routes (e.g. "acme-federation").
        plan: Billing tier for the organisation.
        stripe_customer_id: Stripe customer ID, set when the first Checkout session
            is created. Used to link Stripe webhook events back to this org.
        created_at: UTC timestamp of creation, set automatically.
        memberships: Back-reference to all Membership rows for this org.
        documents: Back-reference to all Document rows owned by this org.
    """

    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plan: Mapped[OrgPlan] = mapped_column(
        Enum(OrgPlan, name="org_plan"), nullable=False, default=OrgPlan.solo
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(  # noqa: F821
        "Membership", back_populates="organisation", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="organisation", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["Invitation"]] = relationship(  # noqa: F821
        "Invitation", back_populates="organisation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organisation id={self.id!r} slug={self.slug!r} plan={self.plan}>"
