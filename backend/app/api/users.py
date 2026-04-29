"""
User stats API — GET /api/users/me/stats

Returns aggregate activity stats for the currently authenticated user:
  - orgs_count:               number of organisations the user belongs to
  - docs_count:               number of documents across those organisations
  - amendments_submitted:     total amendments the user has ever submitted
  - pending_amendments_count: total pending amendments across all orgs the user belongs to
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.amendment import Amendment, AmendmentStatus
from app.models.document import Document
from app.models.membership import Membership
from app.models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])


class UserStatsResponse(BaseModel):
    """Aggregate activity stats for the authenticated user."""

    orgs_count: int
    docs_count: int
    amendments_submitted: int
    pending_amendments_count: int


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserStatsResponse:
    """
    Return activity statistics for the authenticated user.

    Queries:
      - orgs_count:           COUNT of memberships where user_id = current_user.id
      - docs_count:           COUNT of documents in any org where the user is a member
      - amendments_submitted: COUNT of amendments where author_id = current_user.id

    Parameters:
        current_user: Injected via get_current_user dependency.
        db: Injected async DB session.

    Returns:
        UserStatsResponse with the four counters.
    """
    user_id = current_user.id

    # Orgs count — one row per membership
    orgs_result = await db.execute(
        select(func.count()).select_from(Membership).where(Membership.user_id == user_id)
    )
    orgs_count: int = orgs_result.scalar_one()

    # Docs count — documents in any org this user belongs to
    # Subquery: org IDs where user is a member
    member_org_ids = select(Membership.org_id).where(Membership.user_id == user_id).scalar_subquery()
    docs_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.org_id.in_(member_org_ids))
    )
    docs_count: int = docs_result.scalar_one()

    # Amendments submitted — all amendments ever authored by this user
    amendments_result = await db.execute(
        select(func.count()).select_from(Amendment).where(Amendment.author_id == user_id)
    )
    amendments_submitted: int = amendments_result.scalar_one()

    # Pending amendments — across all docs in orgs where user is a member
    pending_result = await db.execute(
        select(func.count(Amendment.id))
        .join(Document, Amendment.doc_id == Document.id)
        .where(
            Document.org_id.in_(member_org_ids),
            Amendment.status == AmendmentStatus.pending,
        )
    )
    pending_amendments_count: int = pending_result.scalar_one()

    return UserStatsResponse(
        orgs_count=orgs_count,
        docs_count=docs_count,
        amendments_submitted=amendments_submitted,
        pending_amendments_count=pending_amendments_count,
    )
