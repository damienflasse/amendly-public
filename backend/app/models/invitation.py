"""
Invitation model — a pending invitation for a user to join an organisation.

Lifecycle:
  created → (email sent) → accepted (user joins the org) | expired (never accepted)

The `token` field holds a URL-safe random string embedded in the invite link.
`accepted_at` is NULL until the invitee clicks the link and the accept_invite
service function creates the corresponding Membership row.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Invitation(Base):
    """
    SQLAlchemy ORM model for an organisation invitation.

    Attributes:
        id: UUID primary key.
        org_id: FK to organisations.id — the org the invitee is being invited into.
        email: Email address of the person being invited.
        token: Unique URL-safe token embedded in the invite link (48 chars).
        created_at: UTC timestamp when the invitation was created.
        expires_at: UTC timestamp after which the invite link is invalid.
        accepted_at: UTC timestamp when the invite was accepted; NULL if pending.
        organisation: Relationship back to the owning Organisation.
    """

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    organisation: Mapped["Organisation"] = relationship(  # noqa: F821
        "Organisation", back_populates="invitations"
    )

    def __repr__(self) -> str:
        return (
            f"<Invitation id={self.id!r} org={self.org_id!r} email={self.email!r}>"
        )
