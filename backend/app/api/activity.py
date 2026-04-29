"""
Activity feed API routes.

Endpoints:
  GET /api/organisations/{slug}/activity?page=N
      — returns a paginated page of activity entries for the organisation.
        Any authenticated member may read the feed.
        Response shape: { items, total, page, page_size }
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.activity import export_activity_csv, list_activity

router = APIRouter(prefix="/api/organisations", tags=["activity"])


@router.get("/{slug}/activity")
async def get_activity(
    slug: str,
    page: int = Query(default=1, ge=1, description="1-based page number"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return a paginated page of activity feed entries for an organisation.

    Entries are ordered newest-first. Each entry contains:
      - id: UUID of the activity log row.
      - action: The action type (e.g. 'amendment_accepted').
      - actor_name: Display name or email of the user who performed the action.
      - doc_title: Title of the related document (null for org-level events).
      - created_at: ISO-8601 UTC timestamp.

    Any authenticated member of the organisation may call this endpoint.
    Returns 404 if the organisation is not found or the caller is not a member,
    to avoid disclosing the existence of private organisations.

    Parameters:
        slug: URL slug of the target organisation.
        page: 1-based page number (default 1).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Dict with keys: items (list), total (int), page (int), page_size (int).

    Raises:
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        return await list_activity(db=db, current_user=current_user, slug=slug, page=page)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{slug}/activity/export")
async def export_activity(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Download the full activity log for an organisation as a CSV file.

    Owner/admin only. Returns all entries (no pagination) ordered newest-first.
    The CSV contains four columns: timestamp, actor, action, document.

    Parameters:
        slug: URL slug of the target organisation.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        CSV file download response (text/csv; UTF-8).

    Raises:
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the org is not found or the user is not a member.
    """
    try:
        csv_content, filename = await export_activity_csv(
            db=db, current_user=current_user, slug=slug
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
