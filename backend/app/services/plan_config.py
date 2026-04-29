"""
PlanConfig service — CRUD operations for plan pricing configuration.

All pricing data is stored in the plan_config table so that platform
administrators can modify prices, limits, and feature lists through the
/admin/pricing UI without code changes or redeployment.

Public helpers:
  - list_plan_configs     → all plans, sorted by base_price_cents ascending
  - get_plan_config_by_name → single plan or None
  - update_plan_config    → partial update via PlanConfigUpdate payload
  - get_document_limit_for_plan → int or None (None = unlimited)
  - get_external_contributor_limit_for_plan → int or None (None = unlimited)

The document.py service calls get_document_limit_for_plan to enforce the
active-document cap at creation time.
"""

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan_config import PlanConfig
from app.schemas.plan_config import PlanConfigResponse, PlanConfigUpdate

_DEFAULT_EXTERNAL_CONTRIBUTOR_LIMITS = {
    "solo": 0,
    "team": 30,
    "organisation": None,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_response(plan: PlanConfig) -> PlanConfigResponse:
    """
    Convert a PlanConfig ORM instance to a PlanConfigResponse schema.

    Parameters:
        plan: SQLAlchemy PlanConfig instance.

    Returns:
        PlanConfigResponse with features parsed from the JSON TEXT column.
    """
    try:
        features: list[str] = json.loads(plan.features) if plan.features else []
    except (ValueError, TypeError):
        features = []

    return PlanConfigResponse(
        plan_name=plan.plan_name,
        base_price_cents=plan.base_price_cents,
        included_users=plan.included_users,
        extra_user_price_cents=plan.extra_user_price_cents,
        max_active_documents=plan.max_active_documents,
        max_external_contributors=plan.max_external_contributors,
        stripe_price_id=plan.stripe_price_id or "",
        stripe_price_id_annual=plan.stripe_price_id_annual or "",
        features=features,
        is_active=plan.is_active,
        updated_at=plan.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def list_plan_configs(
    db: AsyncSession,
    active_only: bool = False,
) -> list[PlanConfigResponse]:
    """
    Return all plan configurations, sorted by ascending base price.

    Parameters:
        db: Async SQLAlchemy session.
        active_only: When True, only returns rows where is_active = TRUE.

    Returns:
        List of PlanConfigResponse objects sorted by base_price_cents.
    """
    stmt = select(PlanConfig).order_by(PlanConfig.base_price_cents.asc())
    if active_only:
        stmt = stmt.where(PlanConfig.is_active.is_(True))
    result = await db.execute(stmt)
    plans = result.scalars().all()
    return [_to_response(p) for p in plans]


async def get_plan_config_by_name(
    db: AsyncSession,
    plan_name: str,
) -> PlanConfigResponse | None:
    """
    Fetch a single plan configuration by its canonical name.

    Parameters:
        db: Async SQLAlchemy session.
        plan_name: One of 'solo', 'team', 'organisation'.

    Returns:
        PlanConfigResponse if found, None otherwise.
    """
    result = await db.execute(
        select(PlanConfig).where(PlanConfig.plan_name == plan_name)
    )
    plan = result.scalar_one_or_none()
    return _to_response(plan) if plan else None


async def update_plan_config(
    db: AsyncSession,
    plan_name: str,
    payload: PlanConfigUpdate,
) -> PlanConfigResponse:
    """
    Partially update a plan configuration row.

    Only fields that are not None in the payload are written.  A value of -1
    for max_active_documents is treated as a sentinel meaning 'set to NULL'
    (unlimited).

    Parameters:
        db: Async SQLAlchemy session.
        plan_name: Canonical name of the plan to update.
        payload: PlanConfigUpdate with optional fields to change.

    Returns:
        Updated PlanConfigResponse.

    Raises:
        ValueError: If no plan with the given name exists.
    """
    result = await db.execute(
        select(PlanConfig).where(PlanConfig.plan_name == plan_name)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise ValueError(f"Plan '{plan_name}' not found.")

    if payload.base_price_cents is not None:
        plan.base_price_cents = payload.base_price_cents
    if payload.included_users is not None:
        plan.included_users = payload.included_users
    if payload.extra_user_price_cents is not None:
        plan.extra_user_price_cents = payload.extra_user_price_cents
    if payload.max_active_documents is not None:
        # -1 sentinel → NULL (unlimited)
        plan.max_active_documents = (
            None if payload.max_active_documents == -1 else payload.max_active_documents
        )
    if payload.max_external_contributors is not None:
        # -1 sentinel → NULL (unlimited)
        plan.max_external_contributors = (
            None
            if payload.max_external_contributors == -1
            else payload.max_external_contributors
        )
    if payload.stripe_price_id is not None:
        plan.stripe_price_id = payload.stripe_price_id
    if payload.stripe_price_id_annual is not None:
        plan.stripe_price_id_annual = payload.stripe_price_id_annual
    if payload.features is not None:
        plan.features = json.dumps(payload.features)
    if payload.is_active is not None:
        plan.is_active = payload.is_active

    plan.updated_at = datetime.now(UTC)
    await db.flush()

    return _to_response(plan)


async def get_document_limit_for_plan(
    db: AsyncSession,
    plan_name: str,
) -> int | None:
    """
    Return the maximum active-document count for a plan, or None if unlimited.

    Parameters:
        db: Async SQLAlchemy session.
        plan_name: Canonical plan name ('solo', 'team', 'organisation').

    Returns:
        Integer limit, or None if the plan has no document cap (or plan not found).
    """
    result = await db.execute(
        select(PlanConfig.max_active_documents).where(PlanConfig.plan_name == plan_name)
    )
    row = result.one_or_none()
    if row is None:
        return None  # unknown plan → no cap (safe default)
    return row[0]  # may be None (unlimited) or an int


async def get_external_contributor_limit_for_plan(
    db: AsyncSession,
    plan_name: str,
) -> int | None:
    """
    Return the distinct external-contributor cap for a plan, or None if unlimited.

    Parameters:
        db: Async SQLAlchemy session.
        plan_name: Canonical plan name ('solo', 'team', 'organisation').

    Returns:
        Integer limit, or None if the plan has no cap.
        Falls back to baked-in defaults when plan_config has not been seeded yet.
    """
    result = await db.execute(
        select(PlanConfig.max_external_contributors).where(PlanConfig.plan_name == plan_name)
    )
    row = result.one_or_none()
    if row is None:
        return _DEFAULT_EXTERNAL_CONTRIBUTOR_LIMITS.get(plan_name)
    return row[0]
