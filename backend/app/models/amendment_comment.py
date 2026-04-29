"""
AmendmentComment model — a threaded discussion comment on an amendment.

Any member of the organisation can post a comment. The comment author or
a moderator (owner/admin) can delete it. Comments are hard-deleted (no
soft-delete) because they carry no lifecycle state.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AmendmentComment(Base):
    """
    SQLAlchemy ORM model for a threaded comment on an amendment.

    Attributes:
        id: UUID primary key.
        amendment_id: FK to amendments.id — the amendment being discussed.
        author_id: FK to users.id — the member who posted the comment. SET NULL
            on user deletion so the comment body is preserved.
        body: Plain-text comment body (max 2 000 chars, enforced at service layer).
        created_at: UTC timestamp, set automatically.
        amendment: Relationship back to the Amendment.
        author: Relationship back to the User.
    """

    __tablename__ = "amendment_comments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    amendment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("amendments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    amendment: Mapped["Amendment"] = relationship(  # noqa: F821
        "Amendment", back_populates="comments"
    )
    author: Mapped["User | None"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<AmendmentComment id={self.id!r} "
            f"amendment={self.amendment_id!r} author={self.author_id!r}>"
        )
