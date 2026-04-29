"""
Activity log service — writing and reading the organisation activity feed.

Writing helpers are thin functions used by other services (amendment, document)
to append rows.  They never raise — a logging failure must never abort the
primary mutation.

The public read function, list_activity, is called by the API route and
returns a paginated page of entries for a given organisation, with just enough
information for the frontend to render "{actor} {action} on {document}".
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityAction, ActivityLog
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Write helpers (fire-and-forget — silently log errors)
# ---------------------------------------------------------------------------


async def log_activity(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    action: ActivityAction,
    doc_id: str | None = None,
    amendment_id: str | None = None,
) -> None:
    """
    Append one entry to the activity log.

    This function is intentionally non-raising: if the INSERT fails for any
    reason the exception is logged but not re-raised so that the calling
    service's primary mutation is not rolled back.

    Parameters:
        db: Async SQLAlchemy session (the same session used by the caller).
        org_id: ID of the owning organisation.
        user_id: ID of the user performing the action.
        action: The ActivityAction enum value.
        doc_id: Optional ID of the document involved.
        amendment_id: Optional ID of the amendment involved.

    Side effects:
        Flushes a new ActivityLog row to the session (committed with the
        caller's transaction).
    """
    try:
        entry = ActivityLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            doc_id=doc_id,
            amendment_id=amendment_id,
        )
        db.add(entry)
        await db.flush()
    except Exception:
        logger.exception(
            "Failed to write activity log entry: org=%s user=%s action=%s",
            org_id,
            user_id,
            action,
        )


# ---------------------------------------------------------------------------
# Read — public feed
# ---------------------------------------------------------------------------


def _format_entry(entry: ActivityLog) -> dict:
    """
    Convert an ActivityLog ORM instance to a JSON-serialisable dict.

    Parameters:
        entry: SQLAlchemy ActivityLog instance (with 'user' and 'document'
               relationships eagerly loaded).

    Returns:
        Dict with keys: id, action, actor_name, doc_title, created_at (ISO-8601).
    """
    actor_name = (
        entry.user.name or entry.user.email
        if entry.user
        else "Unknown"
    )
    doc_title = entry.document.title if entry.document else None

    return {
        "id": entry.id,
        "action": entry.action.value,
        "actor_name": actor_name,
        "doc_title": doc_title,
        "created_at": entry.created_at.isoformat() if isinstance(entry.created_at, datetime) else entry.created_at,
    }


async def list_activity(
    db: AsyncSession,
    current_user: User,
    slug: str,
    page: int = 1,
) -> dict:
    """
    Return a paginated page of activity entries for an organisation.

    Any authenticated member of the organisation may read the feed.
    Returns 404 (via ValueError) if the org is not found or the caller
    is not a member, to avoid disclosing private organisations.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the feed.
        slug: URL slug of the target organisation.
        page: 1-based page number (default 1).

    Returns:
        Dict with keys:
          items     — list of at most PAGE_SIZE dicts (newest first), each with:
                      id, action, actor_name, doc_title, created_at.
          total     — total number of activity log rows for this org.
          page      — current page number.
          page_size — number of items per page.

    Raises:
        ValueError: If the org is not found or the user is not a member.
    """
    # Verify membership
    result = await db.execute(
        select(Organisation, Membership)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")

    org, _ = row

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(ActivityLog).where(ActivityLog.org_id == org.id)
    )
    total = count_result.scalar_one()

    # Paginated rows
    offset = (page - 1) * PAGE_SIZE
    entries_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.org_id == org.id)
        .order_by(ActivityLog.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    entries = entries_result.scalars().all()

    return {
        "items": [_format_entry(e) for e in entries],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
    }


async def export_activity_csv(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> tuple[str, str]:
    """
    Export the full activity log for an organisation as a CSV string.

    Owner/admin only. Fetches all entries (no pagination limit) ordered
    newest-first and serialises them as CSV with columns:
    timestamp, actor, action, document.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the export (owner/admin).
        slug: URL slug of the target organisation.

    Returns:
        Tuple of (csv_content, filename) where csv_content is a UTF-8 string
        suitable for use as a file download body.

    Raises:
        ValueError: If the org is not found, the user is not a member,
                    or the user does not have owner/admin role.
    """
    result = await db.execute(
        select(Organisation, Membership)
        .join(
            Membership,
            (Membership.org_id == Organisation.id) & (Membership.user_id == current_user.id),
        )
        .where(Organisation.slug == slug)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Organisation '{slug}' not found or you are not a member.")

    org, membership = row
    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise ValueError("Only owners and admins can export the activity log.")

    entries_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.org_id == org.id)
        .order_by(ActivityLog.created_at.desc())
    )
    entries = entries_result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(["timestamp", "actor", "action", "document"])
    for entry in entries:
        formatted = _format_entry(entry)
        writer.writerow([
            formatted["created_at"],
            formatted["actor_name"],
            formatted["action"],
            formatted["doc_title"] or "",
        ])

    slug_safe = slug.replace("/", "-")
    filename = f"activity-{slug_safe}.csv"
    return output.getvalue(), filename
