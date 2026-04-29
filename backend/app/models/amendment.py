"""
Amendment model — a proposed change to a document (or a general comment on it).

An amendment has two types:
  text_change    — original_text → proposed_text substitution (classic diff)
  general_comment — free-form comment; no diff; original/proposed text are NULL

Lifecycle:
  pending → accepted | rejected | withdrawn
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AmendmentStatus(str, enum.Enum):
    """Lifecycle stage of an amendment."""

    pending = "pending"       # Submitted; awaiting decision from owner/admin
    accepted = "accepted"     # Incorporated into the consolidated text
    rejected = "rejected"     # Declined; not incorporated
    withdrawn = "withdrawn"   # Retracted by the author; soft-deleted from the process


class AmendmentType(str, enum.Enum):
    """Nature of the amendment — text substitution or general comment."""

    text_change = "text_change"         # Classic diff: original_text → proposed_text
    general_comment = "general_comment" # Free-form comment; no diff required


class Amendment(Base):
    """
    SQLAlchemy ORM model for a document amendment.

    Attributes:
        id: UUID primary key.
        doc_id: FK to documents.id — owning document.
        amendment_type: Nature of the amendment (text_change | general_comment).
        section: Optional free-text label identifying the section being amended.
        original_text: The passage being proposed for change (NULL for general_comment).
        proposed_text: The author's replacement text (NULL for general_comment).
        justification: Optional explanation for text_change; main comment body for
            general_comment (in that case it is required at the service layer).
        decision_reason: Optional explanation provided when accepting or rejecting.
        status: Current lifecycle stage of the amendment.
        author_id: FK to users.id — who submitted the amendment.
        created_at: UTC timestamp of submission, set automatically.
        document: Relationship back to the owning Document.
        author: Relationship back to the submitting User.
    """

    __tablename__ = "amendments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    doc_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amendment_type: Mapped[AmendmentType] = mapped_column(
        Enum(AmendmentType, name="amendment_type"),
        nullable=False,
        default=AmendmentType.text_change,
        server_default="text_change",
    )
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AmendmentStatus] = mapped_column(
        Enum(AmendmentStatus, name="amendment_status"),
        nullable=False,
        default=AmendmentStatus.pending,
    )
    author_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Anonymous contributor fields — populated when author_id is NULL and the
    # amendment was submitted via the public /contribute/{token} endpoint.
    contributor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contributor_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="amendments"
    )
    author: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="amendments"
    )
    reactions: Mapped[list["AmendmentReaction"]] = relationship(  # noqa: F821
        "AmendmentReaction", back_populates="amendment", cascade="all, delete-orphan"
    )
    comments: Mapped[list["AmendmentComment"]] = relationship(  # noqa: F821
        "AmendmentComment", back_populates="amendment", cascade="all, delete-orphan",
        order_by="AmendmentComment.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Amendment id={self.id!r} type={self.amendment_type} "
            f"doc={self.doc_id!r} status={self.status}>"
        )
