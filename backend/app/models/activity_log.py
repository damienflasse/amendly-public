"""
ActivityLog model — append-only audit trail for the most significant events
in an organisation.

One row is written for each of these events:
  - document_created
  - amendment_submitted
  - amendment_accepted
  - amendment_rejected
  - amendment_withdrawn
  - status_changed        (document status updated by owner/admin)
  - amendment_commented   (a comment was posted on an amendment)

All fields are nullable where semantically appropriate so that partial events
(e.g. org-level events with no document) can be stored without dummy IDs.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ActivityAction(str, enum.Enum):
    """Enumeration of recordable activity actions."""

    document_created = "document_created"
    amendment_submitted = "amendment_submitted"
    amendment_accepted = "amendment_accepted"
    amendment_rejected = "amendment_rejected"
    amendment_withdrawn = "amendment_withdrawn"
    status_changed = "status_changed"
    amendment_commented = "amendment_commented"


class ActivityLog(Base):
    """
    SQLAlchemy ORM model for an activity log entry.

    Attributes:
        id: UUID primary key.
        org_id: FK to organisations.id — owning organisation.
        user_id: FK to users.id — the user who performed the action.
        doc_id: FK to documents.id — document involved (nullable).
        amendment_id: FK to amendments.id — amendment involved (nullable).
        action: The type of activity that occurred.
        created_at: UTC timestamp of the event, set automatically.
        user: Relationship to the acting User.
        document: Relationship to the involved Document (optional).
    """

    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    doc_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amendment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("amendments.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[ActivityAction] = mapped_column(
        Enum(ActivityAction, name="activity_action"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships (lazy='joined' is intentional — the activity feed always
    # needs the actor name and document title, so we avoid N+1 by fetching
    # them together with the log entry).
    user: Mapped["User"] = relationship("User", lazy="joined")  # noqa: F821
    document: Mapped["Document | None"] = relationship("Document", lazy="joined")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<ActivityLog id={self.id!r} action={self.action} "
            f"user={self.user_id!r} doc={self.doc_id!r}>"
        )
