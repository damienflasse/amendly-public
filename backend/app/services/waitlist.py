"""
Waitlist service — pre-launch email capture.

Public functions:
  - create_waitlist_entry  → validate, persist, send confirmation email
  - list_waitlist_entries  → ordered list for superadmin
"""

from __future__ import annotations

import logging
import uuid

import resend
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.waitlist import WaitlistEntry
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_schema(entry: WaitlistEntry) -> WaitlistResponse:
    return WaitlistResponse(
        id=entry.id,
        email=entry.email,
        source=entry.source,
        created_at=entry.created_at,
    )


async def _send_confirmation_email(email: str) -> None:
    """Send a plain-text confirmation to the new waitlist subscriber."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping waitlist confirmation email.")
        return

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": settings.resend_prospect_from_email or settings.resend_from_email,
            "to": email,
            "subject": "You're on the Amendly waitlist",
            "text": (
                "Hi,\n\n"
                "Thanks for your interest in Amendly — we've added you to our waitlist.\n\n"
                "We'll reach out as soon as the platform is ready for you.\n\n"
                "In the meantime, feel free to reply to this email if you have questions.\n\n"
                "The Amendly team\n"
                "https://amendly.eu"
            ),
        })
    except Exception:
        # Never let an email failure block the signup response.
        logger.exception("Failed to send waitlist confirmation email to %s", email)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_waitlist_entry(
    db: AsyncSession,
    payload: WaitlistCreate,
) -> WaitlistResponse:
    """
    Persist a new waitlist entry and send a confirmation email.

    Parameters:
        db:      Async database session.
        payload: Validated WaitlistCreate schema.

    Returns:
        WaitlistResponse for the newly created entry.

    Raises:
        ValueError("already_registered"): If the email already exists.
    """
    entry = WaitlistEntry(
        id=str(uuid.uuid4()),
        email=payload.email.lower().strip(),
        source=payload.source,
    )
    db.add(entry)
    try:
        await db.commit()
        await db.refresh(entry)
    except IntegrityError:
        await db.rollback()
        raise ValueError("already_registered")

    await _send_confirmation_email(entry.email)
    return _row_to_schema(entry)


async def list_waitlist_entries(db: AsyncSession) -> list[WaitlistResponse]:
    """
    Return all waitlist entries ordered by signup date (newest first).

    Parameters:
        db: Async database session.

    Returns:
        List of WaitlistResponse.
    """
    result = await db.execute(
        select(WaitlistEntry).order_by(WaitlistEntry.created_at.desc())
    )
    return [_row_to_schema(row) for row in result.scalars().all()]
