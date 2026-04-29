"""
Prospect model — tracks potential customers / sales leads for the superadmin.

Status flow: new → contacted → demo_booked → converted | lost
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProspectStatus(str, enum.Enum):
    """Sales pipeline stage for a prospect."""

    new = "new"
    contacted = "contacted"
    demo_booked = "demo_booked"
    converted = "converted"
    lost = "lost"


class Prospect(Base):
    """
    SQLAlchemy ORM model for a sales prospect.

    Attributes:
        id:           UUID primary key.
        email:        Contact email address.
        name:         Contact full name (optional).
        org_name:     Organisation name (optional).
        notes:        Free-text notes visible only to the superadmin.
        status:       Current pipeline stage (default: new).
        created_at:   Row creation timestamp.
        updated_at:   Last update timestamp.
    """

    __tablename__ = "prospects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    org_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProspectStatus.new.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
