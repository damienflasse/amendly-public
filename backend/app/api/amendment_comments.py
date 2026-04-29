"""
Amendment comment API routes.

Endpoints:
  GET    /api/organisations/{slug}/documents/{doc_id}/amendments/{aid}/comments
      — list all comments on an amendment (any member)
  POST   /api/organisations/{slug}/documents/{doc_id}/amendments/{aid}/comments
      — post a new comment (any member)
  DELETE /api/organisations/{slug}/documents/{doc_id}/amendments/{aid}/comments/{cid}
      — delete a comment (author or owner/admin)

All endpoints enforce membership: non-members receive 404 to avoid disclosing
private organisation contents.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.amendment_comment import CommentCreate, CommentListResponse, CommentResponse
from app.services.amendment_comment import create_comment, delete_comment, list_comments
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/organisations/{slug}/documents/{doc_id}/amendments/{amendment_id}/comments",
    tags=["amendment-comments"],
)


@router.get("", response_model=CommentListResponse)
async def get_comments(
    slug: str,
    doc_id: str,
    amendment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentListResponse:
    """
    List all comments on an amendment, ordered oldest-first.

    Any authenticated member of the organisation may call this endpoint.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the amendment whose comments are requested.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        CommentListResponse with items and total.

    Raises:
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        return await list_comments(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def post_comment(
    slug: str,
    doc_id: str,
    amendment_id: str,
    body: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    """
    Post a new comment on an amendment.

    Any authenticated member of the organisation may comment.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the target amendment.
        body: CommentCreate request body.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        CommentResponse for the newly created comment (201 Created).

    Raises:
        HTTPException 404: If the org/doc/amendment is not found or user is not a member.
    """
    try:
        return await create_comment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
            payload=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_comment(
    slug: str,
    doc_id: str,
    amendment_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a comment. Only the comment author or an org owner/admin may delete.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the owning document.
        amendment_id: UUID of the parent amendment.
        comment_id: UUID of the comment to delete.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        204 No Content on success.

    Raises:
        HTTPException 403: If the user is not the author or a moderator.
        HTTPException 404: If the org/doc/amendment/comment is not found or user is not a member.
    """
    try:
        await delete_comment(
            db=db,
            current_user=current_user,
            slug=slug,
            doc_id=doc_id,
            amendment_id=amendment_id,
            comment_id=comment_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "author" in msg or "moderator" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
