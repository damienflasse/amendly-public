"""
Membership model — join table linking Users to Organisations with a role.

A user can belong to multiple organisations with different roles in each.
The composite primary key (user_id, org_id) enforces one membership per pair.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MemberRole(str, enum.Enum):
    """Role of a user within an organisation."""

    owner = "owner"    # Full control including billing and deletion
    admin = "admin"    # Manage members and documents; cannot delete org
    member = "member"  # Read/write access to documents; no admin capabilities


class Membership(Base):
    """
    SQLAlchemy ORM model for organisation membership.

    Attributes:
        user_id: FK to users.id — part of composite PK.
        org_id: FK to organisations.id — part of composite PK.
        role: The access level this user has within the organisation.
        created_at: UTC timestamp when the membership was created.
        notifications_muted: When True, the user has silenced email notifications
            for this specific organisation. Defaults to False.
        user: Relationship back to the User.
        organisation: Relationship back to the Organisation.
    """

    __tablename__ = "memberships"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role"), nullable=False, default=MemberRole.member
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notifications_muted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memberships")  # noqa: F821
    organisation: Mapped["Organisation"] = relationship(  # noqa: F821
        "Organisation", back_populates="memberships"
    )

    def __repr__(self) -> str:
        return (
            f"<Membership user={self.user_id!r} org={self.org_id!r} role={self.role}>"
        )
