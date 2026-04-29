"""
WaitlistEntry model — captures visitor emails before the public launch.

A waitlist entry is created by an unauthenticated visitor on the landing page.
Duplicate emails are rejected at the DB level (unique constraint) and at the
API level (409 Conflict) so the table stays clean.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WaitlistEntry(Base):
    """
    SQLAlchemy ORM model for a pre-launch waitlist entry.

    Attributes:
        id:         UUID primary key.
        email:      Visitor email address (unique, indexed).
        source:     Optional tag indicating where the signup originated
                    (e.g. "hero", "footer", "blog").  Nullable.
        created_at: Row creation timestamp (UTC).
    """

    __tablename__ = "waitlist_entries"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
