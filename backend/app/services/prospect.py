"""
Prospect service — CRUD and email sending for sales leads managed by the superadmin.

Status flow: new → contacted → demo_booked → converted | lost

Public functions:
  - list_prospects         → ordered list of all prospects
  - create_prospect        → create a new prospect
  - update_prospect        → partially update a prospect
  - delete_prospect        → permanently delete a prospect
  - send_prospect_email    → send a transactional email to a prospect via Resend
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import resend

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.prospect import Prospect, ProspectStatus
from app.schemas.prospect import ProspectCreate, ProspectEmailRequest, ProspectResponse, ProspectUpdate
from app.services.email_template import get_email_template

logger = logging.getLogger(__name__)


def _row_to_schema(p: Prospect) -> ProspectResponse:
    """
    Convert a Prospect ORM instance to a ProspectResponse schema.

    Parameters:
        p: SQLAlchemy Prospect instance.

    Returns:
        ProspectResponse with ISO-8601 datetime strings.
    """
    return ProspectResponse(
        id=p.id,
        email=p.email,
        name=p.name,
        org_name=p.org_name,
        notes=p.notes,
        status=p.status,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


async def list_prospects(db: AsyncSession) -> list[ProspectResponse]:
    """
    Return all prospects ordered newest-first.

    Parameters:
        db: Async SQLAlchemy session.

    Returns:
        List of ProspectResponse objects.
    """
    result = await db.execute(
        select(Prospect).order_by(Prospect.created_at.desc())
    )
    return [_row_to_schema(p) for p in result.scalars().all()]


async def create_prospect(
    db: AsyncSession, body: ProspectCreate
) -> ProspectResponse:
    """
    Create a new prospect.

    Parameters:
        db: Async SQLAlchemy session.
        body: ProspectCreate with required email and optional fields.

    Returns:
        The newly created ProspectResponse.
    """
    prospect = Prospect(
        id=str(uuid.uuid4()),
        email=body.email,
        name=body.name,
        org_name=body.org_name,
        notes=body.notes,
        status=ProspectStatus.new.value,
    )
    db.add(prospect)
    await db.commit()
    await db.refresh(prospect)
    return _row_to_schema(prospect)


async def update_prospect(
    db: AsyncSession, prospect_id: str, body: ProspectUpdate
) -> ProspectResponse:
    """
    Partially update an existing prospect.

    Only non-None fields in body are written.

    Parameters:
        db: Async SQLAlchemy session.
        prospect_id: UUID of the prospect to update.
        body: ProspectUpdate with optional fields.

    Returns:
        Updated ProspectResponse.

    Raises:
        ValueError: If no prospect with the given ID exists.
        ValueError: If the supplied status is not a valid ProspectStatus value.
    """
    result = await db.execute(
        select(Prospect).where(Prospect.id == prospect_id)
    )
    prospect = result.scalar_one_or_none()
    if prospect is None:
        raise ValueError(f"Prospect '{prospect_id}' not found.")

    if body.email is not None:
        prospect.email = body.email
    if body.name is not None:
        prospect.name = body.name
    if body.org_name is not None:
        prospect.org_name = body.org_name
    if body.notes is not None:
        prospect.notes = body.notes
    if body.status is not None:
        valid = {s.value for s in ProspectStatus}
        if body.status not in valid:
            raise ValueError(
                f"Invalid status '{body.status}'. Valid values: {sorted(valid)}"
            )
        prospect.status = body.status

    await db.commit()
    await db.refresh(prospect)
    return _row_to_schema(prospect)


async def delete_prospect(db: AsyncSession, prospect_id: str) -> None:
    """
    Delete a prospect row by ID.

    Parameters:
        db: Async SQLAlchemy session.
        prospect_id: UUID of the prospect to delete.

    Raises:
        ValueError: If no prospect with the given ID exists.
    """
    result = await db.execute(
        select(Prospect).where(Prospect.id == prospect_id)
    )
    prospect = result.scalar_one_or_none()
    if prospect is None:
        raise ValueError(f"Prospect '{prospect_id}' not found.")
    await db.delete(prospect)
    await db.commit()


async def send_prospect_email(
    db: AsyncSession, prospect_id: str, body: ProspectEmailRequest
) -> ProspectResponse:
    """
    Send an email to a prospect via Resend and log it in their notes.

    Either body.template_key resolves a stored template (with {nom} and
    {org_name} substituted from the prospect), or body.subject + body.html_body
    are used as a free-form email.

    Side effects:
      - Sends the email via Resend.
      - Appends a log line to prospect.notes (timestamp + subject).
      - If the prospect status is 'new', advances it to 'contacted'.

    Parameters:
        db: Async SQLAlchemy session.
        prospect_id: UUID of the prospect to email.
        body: ProspectEmailRequest with either template_key or subject+html_body.

    Returns:
        Updated ProspectResponse.

    Raises:
        ValueError: If the prospect is not found.
        ValueError: If neither template_key nor (subject + html_body) are provided.
        ValueError: If the template_key is unknown.
        RuntimeError: If the Resend API call fails.
    """
    # --- Fetch prospect ---
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if prospect is None:
        raise ValueError(f"Prospect '{prospect_id}' not found.")

    variables = {
        "nom": prospect.name or prospect.email,
        "org_name": prospect.org_name or "",
        "contact_email": settings.resend_prospect_from_email or settings.resend_from_email,
        "sender_name": settings.sender_name or "Amendly",
    }

    # --- Resolve subject + html_body ---
    if body.template_key:
        tmpl = await get_email_template(db, body.template_key)
        if tmpl is None:
            raise ValueError(f"Unknown template key: {body.template_key!r}")
        try:
            subject = tmpl.subject.format_map(variables)
            html_body = tmpl.html_body.format_map(variables)
        except KeyError:
            subject = tmpl.subject
            html_body = tmpl.html_body
    elif body.subject and body.html_body:
        try:
            subject = body.subject.format_map(variables)
            html_body = body.html_body.format_map(variables)
        except KeyError:
            subject = body.subject
            html_body = body.html_body
    else:
        raise ValueError(
            "Provide either template_key or both subject and html_body."
        )

    # --- Send via Resend ---
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": f"{settings.sender_name or 'Amendly'} <{settings.resend_prospect_from_email}>",
            "to": [prospect.email],
            "subject": subject,
            "html": html_body,
        })
    except Exception as exc:
        logger.error("Resend failed for prospect %s: %s", prospect_id, exc)
        raise RuntimeError(f"Email delivery failed: {exc}") from exc

    # --- Log in notes ---
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log_line = f"[{timestamp}] Email sent — {subject}"
    if prospect.notes:
        prospect.notes = f"{prospect.notes}\n{log_line}"
    else:
        prospect.notes = log_line

    # --- Auto-advance status new → contacted ---
    if prospect.status == ProspectStatus.new.value:
        prospect.status = ProspectStatus.contacted.value

    await db.commit()
    await db.refresh(prospect)
    return _row_to_schema(prospect)
