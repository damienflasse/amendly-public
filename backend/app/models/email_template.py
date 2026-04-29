"""
EmailTemplate model — stores editable transactional email templates.

Each row represents one email type (template_key is unique).
The html_body field uses {variable} placeholders that are substituted at
send time.  If no row exists for a given key, the hardcoded fallback is used.

Available template keys and their variables:
  invite              — {org_name}, {invite_url}, {inviter_name}
  amendment_accepted  — {org_name}, {doc_title}, {section}, {doc_url}
  amendment_rejected  — {org_name}, {doc_title}, {section}, {doc_url}
  magic_link          — {magic_link_url}
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailTemplate(Base):
    """
    Persisted email template editable by the platform superadmin.

    Attributes:
        id:           UUID primary key.
        template_key: Unique identifier for this email type (e.g. 'invite').
        subject:      Email subject line — may contain {variable} placeholders.
        html_body:    Full HTML email body — may contain {variable} placeholders.
        updated_at:   Timestamp of last edit (auto-updated on write).
    """

    __tablename__ = "email_templates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    template_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
