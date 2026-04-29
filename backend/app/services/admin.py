"""
Admin service — platform-level statistics and organisation management for superusers.

Public functions:
  - get_platform_stats      → aggregated counts + estimated MRR + amendments + sparkline
  - list_all_organisations  → all orgs enriched with member/document/amendment counts
  - update_org_plan         → override an org's billing plan (extension or revocation)
  - list_all_users          → all users with org membership info, filterable
  - update_user             → override a user's plan and/or plan_expires_at
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.amendment import Amendment
from app.models.document import Document, DocumentStatus
from app.models.membership import Membership
from app.models.organisation import OrgPlan, Organisation
from app.models.plan_config import PlanConfig
from app.models.user import User, UserPlan
from app.schemas.admin import AdminOrgResponse, AdminStatsResponse, AdminUserResponse, OrgRegistrationPoint

VALID_PLANS = {p.value for p in OrgPlan}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_org(
    org: Organisation,
    member_count: int,
    document_count: int,
    amendment_count: int,
    last_activity_at: datetime | None,
) -> AdminOrgResponse:
    """
    Convert an Organisation ORM instance plus computed counts to AdminOrgResponse.

    Parameters:
        org: SQLAlchemy Organisation instance.
        member_count: Pre-computed number of active memberships.
        document_count: Pre-computed number of documents.
        amendment_count: Pre-computed number of amendments across all org documents.
        last_activity_at: Latest amendment or document created_at timestamp (or None).

    Returns:
        AdminOrgResponse ready for serialisation.
    """
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan.value,
        member_count=member_count,
        document_count=document_count,
        amendment_count=amendment_count,
        last_activity_at=last_activity_at.isoformat() if last_activity_at else None,
        stripe_customer_id=org.stripe_customer_id,
        created_at=org.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def get_platform_stats(db: AsyncSession) -> AdminStatsResponse:
    """
    Return aggregated platform-level statistics.

    Computes:
      - total_orgs: count of all organisations.
      - total_users: count of all non-deleted users.
      - orgs_by_plan: breakdown of org count per plan tier.
      - estimated_mrr_cents: sum of (orgs_per_plan × plan.base_price_cents).
        Solo is priced at 0 by convention. Uses the plan_config table prices.

    Parameters:
        db: Async SQLAlchemy session.

    Returns:
        AdminStatsResponse with the computed fields.
    """
    # Total orgs
    org_count_result = await db.execute(select(func.count()).select_from(Organisation))
    total_orgs: int = org_count_result.scalar_one()

    # Total users (non-deleted)
    user_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.is_deleted.is_(False))
    )
    total_users: int = user_count_result.scalar_one()

    # Orgs grouped by plan
    plan_group_result = await db.execute(
        select(Organisation.plan, func.count(Organisation.id).label("cnt"))
        .group_by(Organisation.plan)
    )
    orgs_by_plan: dict[str, int] = {
        row.plan.value: row.cnt
        for row in plan_group_result
    }
    # Ensure all plan tiers appear in the dict even if count is 0
    for plan in OrgPlan:
        orgs_by_plan.setdefault(plan.value, 0)

    # Fetch plan prices for MRR estimate
    price_result = await db.execute(
        select(PlanConfig.plan_name, PlanConfig.base_price_cents)
    )
    price_map: dict[str, int] = {row.plan_name: row.base_price_cents for row in price_result}

    estimated_mrr_cents = sum(
        orgs_by_plan.get(plan_name, 0) * price_map.get(plan_name, 0)
        for plan_name in VALID_PLANS
    )

    # Total amendments (all statuses, all orgs)
    amendment_count_result = await db.execute(
        select(func.count()).select_from(Amendment)
    )
    total_amendments: int = amendment_count_result.scalar_one()

    # Total open documents
    open_doc_result = await db.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.status == DocumentStatus.open.value)
    )
    total_open_documents: int = open_doc_result.scalar_one()

    # Org registrations over the last 30 days (inclusive of today)
    cutoff = datetime.now(timezone.utc) - timedelta(days=29)
    reg_result = await db.execute(
        select(
            cast(Organisation.created_at, Date).label("day"),
            func.count(Organisation.id).label("cnt"),
        )
        .where(Organisation.created_at >= cutoff)
        .group_by(cast(Organisation.created_at, Date))
        .order_by(cast(Organisation.created_at, Date))
    )
    day_counts: dict[str, int] = {row.day.isoformat(): row.cnt for row in reg_result}

    # Fill in zero-count days for the full 30-day window
    today = datetime.now(timezone.utc).date()
    orgs_last_30_days: list[OrgRegistrationPoint] = []
    for offset in range(29, -1, -1):
        d = (today - timedelta(days=offset)).isoformat()
        orgs_last_30_days.append(OrgRegistrationPoint(date=d, count=day_counts.get(d, 0)))

    return AdminStatsResponse(
        total_orgs=total_orgs,
        total_users=total_users,
        orgs_by_plan=orgs_by_plan,
        estimated_mrr_cents=estimated_mrr_cents,
        total_amendments=total_amendments,
        total_open_documents=total_open_documents,
        orgs_last_30_days=orgs_last_30_days,
    )


async def list_all_organisations(db: AsyncSession) -> list[AdminOrgResponse]:
    """
    Return all organisations enriched with member, document, and amendment counts,
    plus the date of last activity (newest amendment or document).

    Uses correlated subqueries so no N+1 queries are issued.
    Results are ordered by creation date, newest first.

    Parameters:
        db: Async SQLAlchemy session.

    Returns:
        List of AdminOrgResponse objects.
    """
    member_subq = (
        select(func.count(Membership.user_id))
        .where(Membership.org_id == Organisation.id)
        .correlate(Organisation)
        .scalar_subquery()
    )
    doc_subq = (
        select(func.count(Document.id))
        .where(Document.org_id == Organisation.id)
        .correlate(Organisation)
        .scalar_subquery()
    )
    # Amendments submitted across all documents belonging to this org
    amendment_subq = (
        select(func.count(Amendment.id))
        .join(Document, Amendment.doc_id == Document.id)
        .where(Document.org_id == Organisation.id)
        .correlate(Organisation)
        .scalar_subquery()
    )
    # Latest activity: max(created_at) across amendments and documents for this org
    latest_amendment_subq = (
        select(func.max(Amendment.created_at))
        .join(Document, Amendment.doc_id == Document.id)
        .where(Document.org_id == Organisation.id)
        .correlate(Organisation)
        .scalar_subquery()
    )
    latest_doc_subq = (
        select(func.max(Document.created_at))
        .where(Document.org_id == Organisation.id)
        .correlate(Organisation)
        .scalar_subquery()
    )
    last_activity_subq = func.greatest(latest_amendment_subq, latest_doc_subq)

    result = await db.execute(
        select(
            Organisation,
            member_subq.label("member_count"),
            doc_subq.label("doc_count"),
            amendment_subq.label("amendment_count"),
            last_activity_subq.label("last_activity_at"),
        )
        .order_by(Organisation.created_at.desc())
    )

    return [
        _format_org(
            org,
            member_count=mc,
            document_count=dc,
            amendment_count=amc,
            last_activity_at=last_act,
        )
        for org, mc, dc, amc, last_act in result
    ]


async def update_org_plan(
    db: AsyncSession,
    org_id: str,
    new_plan: str,
) -> AdminOrgResponse:
    """
    Override the billing plan of an organisation (extension or revocation).

    An "extension" upgrades the plan (e.g. solo → team).
    A "revocation" downgrades it back to solo (cancelling access to paid features).
    This is a direct database override — it does not interact with Stripe.

    Parameters:
        db: Async SQLAlchemy session.
        org_id: UUID of the organisation to update.
        new_plan: New plan name — must be one of 'solo', 'team', 'organisation'.

    Returns:
        Updated AdminOrgResponse.

    Raises:
        ValueError: If the org is not found or the plan value is invalid.
    """
    if new_plan not in VALID_PLANS:
        raise ValueError(f"Invalid plan '{new_plan}'. Valid values: {sorted(VALID_PLANS)}.")

    # Fetch org
    org_result = await db.execute(
        select(Organisation).where(Organisation.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError(f"Organisation '{org_id}' not found.")

    # Apply the plan change
    org.plan = OrgPlan(new_plan)
    await db.flush()

    # Re-fetch counts for the response (run in parallel)
    mc_result, dc_result, amc_result, latest_amd, latest_doc = await asyncio.gather(
        db.execute(select(func.count(Membership.user_id)).where(Membership.org_id == org.id)),
        db.execute(select(func.count(Document.id)).where(Document.org_id == org.id)),
        db.execute(
            select(func.count(Amendment.id))
            .join(Document, Amendment.doc_id == Document.id)
            .where(Document.org_id == org.id)
        ),
        db.execute(
            select(func.max(Amendment.created_at))
            .join(Document, Amendment.doc_id == Document.id)
            .where(Document.org_id == org.id)
        ),
        db.execute(select(func.max(Document.created_at)).where(Document.org_id == org.id)),
    )
    la_amd = latest_amd.scalar_one_or_none()
    la_doc = latest_doc.scalar_one_or_none()
    last_activity = max(filter(None, [la_amd, la_doc]), default=None)

    return _format_org(
        org,
        member_count=mc_result.scalar_one(),
        document_count=dc_result.scalar_one(),
        amendment_count=amc_result.scalar_one(),
        last_activity_at=last_activity,
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


def _format_user(user: User, org_names: list[str]) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        company=user.company,
        plan=user.plan.value,
        plan_expires_at=user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        created_at=user.created_at.isoformat(),
        is_deleted=user.is_deleted,
        is_superuser=user.is_superuser,
        org_count=len(org_names),
        org_names=org_names,
    )


async def list_all_users(
    db: AsyncSession,
    *,
    search: str | None = None,
    plan: str | None = None,
    include_deleted: bool = False,
) -> list[AdminUserResponse]:
    """
    Return all users with their org memberships, optionally filtered.

    Parameters:
        db: Async SQLAlchemy session.
        search: Optional substring to match against email or name (case-insensitive).
        plan: Optional plan value to filter by ('solo', 'team', 'organisation').
        include_deleted: When True, include soft-deleted accounts.

    Returns:
        List of AdminUserResponse ordered by created_at desc.
    """
    stmt = select(User).order_by(User.created_at.desc())
    if not include_deleted:
        stmt = stmt.where(User.is_deleted.is_(False))
    if plan:
        stmt = stmt.where(User.plan == UserPlan(plan))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            User.email.ilike(pattern) | User.name.ilike(pattern)
        )

    result = await db.execute(stmt)
    users = result.scalars().all()

    if not users:
        return []

    user_ids = [u.id for u in users]

    # Fetch org names per user in one query
    org_result = await db.execute(
        select(Membership.user_id, Organisation.name)
        .join(Organisation, Membership.org_id == Organisation.id)
        .where(Membership.user_id.in_(user_ids))
    )
    org_map: dict[str, list[str]] = {}
    for user_id, org_name in org_result:
        org_map.setdefault(user_id, []).append(org_name)

    return [_format_user(u, org_map.get(u.id, [])) for u in users]


VALID_USER_PLANS = {p.value for p in UserPlan}


async def update_user(
    db: AsyncSession,
    user_id: str,
    *,
    plan: str | None = None,
    plan_expires_at: datetime | None | str = ...,  # type: ignore[assignment]
) -> AdminUserResponse:
    """
    Override a user's plan and/or plan_expires_at.

    Passing plan_expires_at=None clears the expiry (no expiry).
    Omitting plan_expires_at (sentinel ...) leaves the current value unchanged.

    Parameters:
        db: Async SQLAlchemy session.
        user_id: UUID of the user to update.
        plan: New plan value, or None to leave unchanged.
        plan_expires_at: New expiry datetime, None to clear, or ... to leave unchanged.

    Returns:
        Updated AdminUserResponse.

    Raises:
        ValueError: If the user is not found or plan value is invalid.
    """
    if plan is not None and plan not in VALID_USER_PLANS:
        raise ValueError(f"Invalid plan '{plan}'. Valid values: {sorted(VALID_USER_PLANS)}.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User '{user_id}' not found.")

    if plan is not None:
        user.plan = UserPlan(plan)

    # Sentinel check: only update plan_expires_at if explicitly passed
    if plan_expires_at is not ...:
        if isinstance(plan_expires_at, str):
            if plan_expires_at:
                dt = datetime.fromisoformat(plan_expires_at)
                user.plan_expires_at = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
            else:
                user.plan_expires_at = None
        else:
            user.plan_expires_at = plan_expires_at

    await db.flush()

    org_result = await db.execute(
        select(Organisation.name)
        .join(Membership, Membership.org_id == Organisation.id)
        .where(Membership.user_id == user.id)
    )
    org_names = [row[0] for row in org_result]
    return _format_user(user, org_names)
