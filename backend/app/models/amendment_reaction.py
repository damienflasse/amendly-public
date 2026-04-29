"""
AmendmentReaction model — a member vote (support / oppose) on an amendment.

One reaction per user per amendment (enforced by unique constraint).
Toggle semantics: posting the same type a second time cancels the reaction;
posting the opposite type replaces it. Handled in the service layer.

Plan gating: reactions are only available on the organisation plan.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReactionType(str, enum.Enum):
    """Type of member reaction on an amendment."""

    support = "support"   # +1 — member supports the amendment
    oppose = "oppose"     # -1 — member opposes the amendment


class AmendmentReaction(Base):
    """
    SQLAlchemy ORM model for a member reaction on an amendment.

    Attributes:
        id: UUID primary key.
        user_id: FK to users.id — the member who reacted.
        amendment_id: FK to amendments.id — the amendment being reacted to.
        reaction_type: The nature of the reaction (support | oppose).
        created_at: UTC timestamp of the reaction, set automatically.
        user: Relationship back to the reacting User.
        amendment: Relationship back to the Amendment.
    """

    __tablename__ = "amendment_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "amendment_id", name="uq_reaction_user_amendment"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amendment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("amendments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction_type: Mapped[ReactionType] = mapped_column(
        Enum(ReactionType, name="reaction_type"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User")  # noqa: F821
    amendment: Mapped["Amendment"] = relationship(  # noqa: F821
        "Amendment", back_populates="reactions"
    )

    def __repr__(self) -> str:
        return (
            f"<AmendmentReaction amendment={self.amendment_id!r} "
            f"user={self.user_id!r} type={self.reaction_type}>"
        )
