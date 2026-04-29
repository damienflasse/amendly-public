"""
Amendment API routes — scoped under /api/organisations/{slug}/documents/{doc_id}/amendments.

Endpoints:
  POST /api/organisations/{slug}/documents/{doc_id}/amendments
      — submit an amendment (any member)
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments
      — list amendments (paginated, 20/page, any member)
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments/mine
      — list only the current user's amendments (paginated, 20/page, any member)
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}
      — fetch one amendment (any member)
  PUT  /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}/status
      — accept or reject (owner/admin only)
  GET  /api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}/diff
      — word-level diff between original_text and proposed_text (any member)
  GET  /api/organisations/{slug}/documents/{doc_id}/reaction-summary
      — aggregated support/oppose counts across all pending amendments (team/org plan; owner/admin only)

All endpoints enforce membership: non-members receive 404 to avoid disclosing
the existence of private organisations and their documents.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.amendment import (
    AmendmentCreate,
    AmendmentListResponse,
    AmendmentResponse,
    AmendmentStatusUpdate,
    BulkAmendmentStatusUpdate,
    ReactRequest,
    ReactionSummaryResponse,
)
from app.services.amendment import (
    bulk_update_amendment_status,
    create_amendment,
    get_amendment,
    get_reaction_summary,
    list_amendments,
    list_mine_amendments,
    react_to_amendment,
    update_amendment_status,
    withdraw_amendment,
)
from app.utils.diff import DiffToken, compute_diff


class DiffResponse(BaseModel):
    """Response body for the diff endpoint.

    Attributes:
        tokens: Ordered list of word-level diff tokens covering both the
            original and proposed text.
    """

    tokens: list[DiffToken]

router = APIRouter(
    prefix="/api/organisations/{slug}/documents/{doc_id}/amendments",
    tags=["amendments"],
)

# Separate router for document-level amendment aggregates (different URL prefix)
doc_router = APIRouter(
    prefix="/api/organisations/{slug}/documents/{doc_id}",
    tags=["amendments"],
)


@router.post("", response_model=AmendmentResponse, status_code=status.HTTP_201_CREATED)
async def post_amendment(
    slug: str,
    doc_id: str,
    body: AmendmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentResponse:
    """
    Submit a new amendment to a document.

    Any authenticated member of the organisation may submit an amendment.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        body: AmendmentCreate request body.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentResponse for the newly created amendment (201 Created).

    Raises:
        HTTPException 404: If the org/document is not found or the user is not a member.
    """
    try:
        return await create_amendment(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, payload=body
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=AmendmentListResponse)
async def get_amendments(
    slug: str,
    doc_id: str,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentListResponse:
    """
    List amendments for a document, paginated at 20 per page.

    Non-members receive 404 to avoid disclosing private org contents.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        page: Page number (1-based, default 1).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentListResponse with items, total, page, and page_size.

    Raises:
        HTTPException 404: If the org/document is not found or user is not a member.
    """
    try:
        return await list_amendments(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, page=page
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/mine", response_model=AmendmentListResponse)
async def get_my_amendments(
    slug: str,
    doc_id: str,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentListResponse:
    """
    List the current user's own amendments for a document, paginated at 20 per page.

    Returns only amendments authored by the authenticated caller. Ordered by
    most-recently submitted first. Any member may call this endpoint.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        page: Page number (1-based, default 1).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentListResponse with items, total, page, and page_size.

    Raises:
        HTTPException 404: If the org/document is not found or user is not a member.
    """
    try:
        return await list_mine_amendments(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, page=page
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{amendment_id}", response_model=AmendmentResponse)
async def get_amendment_by_id(
    slug: str,
    doc_id: str,
    amendment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentResponse:
    """
    Fetch a single amendment by its ID.

    Returns 404 when the amendment does not exist or the user is not a member.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the target amendment.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentResponse for the matching amendment.

    Raises:
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        return await get_amendment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{amendment_id}/status", response_model=AmendmentResponse)
async def put_amendment_status(
    slug: str,
    doc_id: str,
    amendment_id: str,
    body: AmendmentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentResponse:
    """
    Accept or reject an amendment. Requires owner or admin role.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the amendment to update.
        body: AmendmentStatusUpdate request body (status: accepted | rejected).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentResponse with the updated status.

    Raises:
        HTTPException 403: If the user lacks write access (member role).
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        return await update_amendment_status(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
            payload=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        if "Only pending" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.patch("/bulk-status")
async def patch_amendments_bulk_status(
    slug: str,
    doc_id: str,
    body: BulkAmendmentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accept or reject multiple pending amendments in one request.

    Only pending amendments are updated; non-pending IDs are silently skipped.
    Activity log entries are written for each updated amendment.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        body: BulkAmendmentStatusUpdate request body.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        Dict with updated_count and skipped_count.

    Raises:
        HTTPException 403: If the user lacks write access (member role).
        HTTPException 404: If the org/document is not found or user is not a member.
    """
    try:
        return await bulk_update_amendment_status(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            payload=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.get("/{amendment_id}/diff", response_model=DiffResponse)
async def get_amendment_diff(
    slug: str,
    doc_id: str,
    amendment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiffResponse:
    """
    Return a word-level diff between an amendment's original and proposed text.

    The amendment is fetched from the database (enforcing membership checks),
    then ``compute_diff`` is called on its ``original_text`` and
    ``proposed_text`` fields.  The result is a list of tokens each labelled
    ``equal``, ``insert``, or ``delete`` — ready to render inline in the UI.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the amendment whose diff is requested.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DiffResponse containing an ordered ``tokens`` list.

    Raises:
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        amendment = await get_amendment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # General comments have no original/proposed text — return empty diff
    if amendment.amendment_type == "general_comment":
        return DiffResponse(tokens=[])

    tokens = compute_diff(
        amendment.original_text or "",
        amendment.proposed_text or "",
    )
    return DiffResponse(tokens=tokens)


@router.post("/{amendment_id}/react", response_model=AmendmentResponse)
async def post_amendment_react(
    slug: str,
    doc_id: str,
    amendment_id: str,
    body: ReactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AmendmentResponse:
    """
    Record, update, or cancel a reaction (support / oppose) on an amendment.

    Toggle semantics: posting the same type twice cancels the reaction.
    Posting the opposite type replaces the previous reaction.

    Plan gating: requires the Organisation plan.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the target amendment.
        body: ReactRequest body (type: 'support' | 'oppose').
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        AmendmentResponse with updated support_count, oppose_count, user_reaction.

    Raises:
        HTTPException 402: If the organisation is not on the Organisation plan.
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        return await react_to_amendment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
            payload=body,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Organisation plan" in msg:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.delete("/{amendment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_amendment(
    slug: str,
    doc_id: str,
    amendment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Withdraw a pending amendment. Author only; only pending amendments can be withdrawn.

    The amendment row is kept in the database with status='withdrawn' (soft-delete)
    so that history is preserved.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the amendment to withdraw.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 403: If the current user is not the amendment's author, or
                           if the amendment is not in 'pending' status.
        HTTPException 404: If the org/document/amendment is not found or the
                           user is not a member.
    """
    try:
        await withdraw_amendment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "author" in msg or "pending" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@doc_router.get("/reaction-summary", response_model=ReactionSummaryResponse)
async def get_document_reaction_summary(
    slug: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReactionSummaryResponse:
    """
    Return aggregated support/oppose reaction counts across all pending amendments.

    Intended for document owners and admins to get a quick read of member sentiment
    before making moderation decisions.

    Plan gating: returns 402 for organisations on the solo plan.
    Role gating: returns 403 for members who are not owner/admin.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        ReactionSummaryResponse with total_pending, support_count, and oppose_count.

    Raises:
        HTTPException 402: If the organisation is not on the Organisation plan.
        HTTPException 403: If the caller is not an owner or admin.
        HTTPException 404: If the org/document is not found or user is not a member.
    """
    try:
        return await get_reaction_summary(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "Organisation plan" in msg:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=msg) from exc
        if "owners and admins" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
