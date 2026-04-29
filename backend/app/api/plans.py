"""
Public plans API — exposes plan configuration data to unauthenticated clients.

Endpoints:
  GET /api/plans  — returns the list of active plan configurations.

This endpoint is intentionally unauthenticated so that the landing page and
pricing page can fetch current prices without requiring a session.  Only rows
where is_active = TRUE are returned.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.plan_config import PlanConfigResponse
from app.services.plan_config import list_plan_configs

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get(
    "",
    response_model=list[PlanConfigResponse],
    summary="List active plan configurations (public)",
)
async def get_plans(
    db: AsyncSession = Depends(get_db),
) -> list[PlanConfigResponse]:
    """
    Return all active plan configurations, sorted by price ascending.

    This endpoint is public and requires no authentication.  The frontend
    (landing page, pricing page, billing page) uses it to render pricing cards
    with up-to-date prices and feature lists.

    Parameters:
        db: Injected async DB session.

    Returns:
        List of PlanConfigResponse objects (only is_active=True rows).
    """
    return await list_plan_configs(db, active_only=True)
