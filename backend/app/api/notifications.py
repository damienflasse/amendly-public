"""
Notification API routes.

In-app notification center and email notification settings for authenticated users.

Notifications are sourced from the existing activity_log table and filtered
to events that occurred in organisations where:
  1. The current user is a member.
  2. The organisation is on a team or organisation plan (premium feature).
  3. The action was performed by someone *other* than the current user.

Targeting:
  amendment_commented entries are only delivered to the amendment's author
  (the person whose amendment was commented on), not to all org members.

Plan gating:
  Solo-plan-only users receive has_team_plan=False and an empty items list.
  The frontend shows an upgrade nudge in that case.

Read tracking:
  users.notifications_last_read_at is a single timestamp marking the last
  moment the user acknowledged their notification feed.  Any activity entry
  created after that timestamp is counted as unread.

Endpoints:
  GET  /api/me/notifications          — list notifications (newest first)
  POST /api/me/notifications/read     — mark all as read (update timestamp)
  GET  /api/me/notifications/settings — global + per-org email notification settings
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.activity_log import ActivityAction, ActivityLog
from app.models.amendment import Amendment
from app.models.membership import Membership
from app.models.organisation import OrgPlan, Organisation
from app.models.user import User

# ---------------------------------------------------------------------------
# Notification settings endpoint
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me/notifications", tags=["notifications"])

# Plans that unlock the notification center
_PREMIUM_PLANS = {OrgPlan.team, OrgPlan.organisation}

# Maximum items returned in one request
_LIMIT_MAX = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_item(entry: ActivityLog, org_name: str, org_slug: str, is_read: bool) -> dict:
    """
    Serialise one ActivityLog row to a notification dict.

    Parameters:
        entry: ActivityLog ORM instance (user and document relationships eagerly loaded).
        org_name: Display name of the owning organisation.
        org_slug: URL slug of the owning organisation (used for client-side routing).
        is_read: True when entry.created_at <= user.notifications_last_read_at.

    Returns:
        Dict with keys: id, action, actor_name, doc_title, doc_id, amendment_id,
        org_name, org_slug, created_at (ISO-8601 string), is_read.
    """
    actor_name = (entry.user.name or entry.user.email) if entry.user else "Unknown"
    doc_title = entry.document.title if entry.document else None

    return {
        "id": entry.id,
        "action": entry.action.value,
        "actor_name": actor_name,
        "doc_title": doc_title,
        "doc_id": entry.doc_id,
        "amendment_id": entry.amendment_id,
        "org_name": org_name,
        "org_slug": org_slug,
        "created_at": (
            entry.created_at.isoformat()
            if isinstance(entry.created_at, datetime)
            else entry.created_at
        ),
        "is_read": is_read,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=_LIMIT_MAX),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return recent notifications for the authenticated user.

    Notifications are activity_log entries from team/organisation-plan orgs
    the user is a member of, excluding actions the user performed themselves.

    Targeting rules:
      - amendment_commented: only shown to the amendment's author (targeted
        notification for the person whose amendment was commented on).
      - all other actions: shown to every member of the org (activity feed).

    Parameters:
        limit: Maximum number of items to return (1–50, default 20).
        current_user: Injected authenticated user.
        db: Injected async DB session.

    Returns:
        Dict with keys:
          has_team_plan — bool: True if the user belongs to at least one
                          team+ org.  False triggers an upgrade nudge in the UI.
          items         — list of notification dicts (newest first).
          unread_count  — int: entries newer than notifications_last_read_at.
    """
    # Find the user's premium orgs (team or organisation plan)
    memberships_result = await db.execute(
        select(Organisation, Membership)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(
            Membership.user_id == current_user.id,
            Organisation.plan.in_(_PREMIUM_PLANS),
        )
    )
    rows = memberships_result.all()

    if not rows:
        return {"has_team_plan": False, "items": [], "unread_count": 0}

    premium_org_ids = [org.id for org, _ in rows]
    org_meta = {org.id: (org.name, org.slug) for org, _ in rows}

    # Fetch activity entries from those orgs, excluding own actions.
    # For amendment_commented, restrict to entries where the current user is
    # the amendment's author (targeted notification to the person commented on).
    comment_targeted = exists(
        select(Amendment.id).where(
            Amendment.id == ActivityLog.amendment_id,
            Amendment.author_id == current_user.id,
        )
    )
    entries_result = await db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.org_id.in_(premium_org_ids),
            ActivityLog.user_id != current_user.id,
            or_(
                ActivityLog.action != ActivityAction.amendment_commented,
                comment_targeted,
            ),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    entries = entries_result.scalars().all()

    last_read = current_user.notifications_last_read_at
    unread_count = sum(
        1
        for e in entries
        if last_read is None or (
            isinstance(e.created_at, datetime)
            and e.created_at.replace(tzinfo=UTC) > last_read.replace(tzinfo=UTC)
        )
    )

    items = [
        _format_item(
            entry=e,
            org_name=org_meta[e.org_id][0],
            org_slug=org_meta[e.org_id][1],
            is_read=(
                last_read is not None
                and isinstance(e.created_at, datetime)
                and e.created_at.replace(tzinfo=UTC) <= last_read.replace(tzinfo=UTC)
            ),
        )
        for e in entries
    ]

    return {"has_team_plan": True, "items": items, "unread_count": unread_count}


@router.post("/read")
async def mark_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Mark all notifications as read by updating notifications_last_read_at to now.

    Parameters:
        current_user: Injected authenticated user.
        db: Injected async DB session.

    Returns:
        Dict: { "ok": True }

    Side effects:
        Updates users.notifications_last_read_at for the current user.
    """
    now = datetime.now(UTC)
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(notifications_last_read_at=now)
    )
    return {"ok": True}


@router.get("/settings")
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return the caller's email notification settings — global flag and per-org mute states.

    The global flag (email_notifications_enabled) applies to all amendment-status
    emails across every organisation.  Per-org mute (notifications_muted) silences
    notifications for a single org while leaving the others active.

    Parameters:
        current_user: Injected authenticated user.
        db: Injected async DB session.

    Returns:
        Dict with keys:
          email_notifications_enabled — bool: global opt-in flag from users table.
          orgs — list of dicts, each with:
            slug          — str: org URL slug (used as the PATCH key).
            name          — str: display name of the organisation.
            notifications_muted — bool: True if the user silenced this org.
    """
    result = await db.execute(
        select(Organisation, Membership)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(Membership.user_id == current_user.id)
        .order_by(Organisation.name)
    )
    rows = result.all()

    orgs = [
        {
            "slug": org.slug,
            "name": org.name,
            "notifications_muted": membership.notifications_muted,
        }
        for org, membership in rows
    ]

    return {
        "email_notifications_enabled": current_user.email_notifications_enabled,
        "orgs": orgs,
    }
