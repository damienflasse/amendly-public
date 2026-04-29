"""
Document model — a text document within an organisation that can receive amendments.

A document goes through a lifecycle: draft (being set up) → open (accepting
amendments) → closed (no more amendments; ready for export).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Lifecycle stage of a document."""

    draft = "draft"    # Created but not yet open for amendments
    open = "open"      # Actively accepting amendments from contributors
    closed = "closed"  # Amendment period ended; document is being finalised


class Document(Base):
    """
    SQLAlchemy ORM model for an amendment document.

    Attributes:
        id: UUID primary key.
        org_id: FK to organisations.id — owning organisation.
        title: Human-readable document title displayed in the dashboard.
        body: The full text of the original document (stored as plain text / Markdown).
        status: Current lifecycle stage of the document.
        created_at: UTC timestamp of creation, set automatically.
        organisation: Relationship back to the owning Organisation.
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_contributor_token", "contributor_token", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.draft,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Contributor public link — token is NULL when no link has been generated.
    contributor_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contributor_token_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contributor_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    organisation: Mapped["Organisation"] = relationship(  # noqa: F821
        "Organisation", back_populates="documents"
    )
    amendments: Mapped[list["Amendment"]] = relationship(  # noqa: F821
        "Amendment", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id!r} title={self.title!r} status={self.status}>"
