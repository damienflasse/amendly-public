"""
Amendment comment service — business logic for the comment thread feature.

Rules:
  - Any authenticated member may list or post comments.
  - A comment may be deleted by its author or by an org owner/admin.
  - Membership is always verified before any operation.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityAction
from app.models.amendment import Amendment
from app.models.amendment_comment import AmendmentComment
from app.models.document import Document
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.schemas.amendment_comment import CommentCreate, CommentListResponse, CommentResponse
from app.services.activity import log_activity
from app.utils.email import send_amendment_commented_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _require_membership(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> tuple[Organisation, Membership]:
    """
    Verify that current_user is a member of the org identified by slug.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user.
        slug: Organisation URL slug.

    Returns:
        Tuple of (Organisation, Membership).

    Raises:
        ValueError: If the organisation is not found or the user is not a member.
    """
    org_result = await db.execute(
        select(Organisation).where(Organisation.slug == slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        raise ValueError("Organisation not found")

    membership_result = await db.execute(
        select(Membership).where(
            Membership.org_id == org.id,
            Membership.user_id == current_user.id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise ValueError("Not a member of this organisation")

    return org, membership


async def _require_amendment(
    db: AsyncSession,
    org: Organisation,
    doc_id: str,
    amendment_id: str,
) -> Amendment:
    """
    Verify that the amendment exists and belongs to the org's document.

    Parameters:
        db: Async SQLAlchemy session.
        org: The owning organisation.
        doc_id: UUID of the parent document.
        amendment_id: UUID of the amendment.

    Returns:
        The Amendment ORM instance.

    Raises:
        ValueError: If the document or amendment is not found.
    """
    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org.id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise ValueError("Document not found")

    amendment_result = await db.execute(
        select(Amendment).where(Amendment.id == amendment_id, Amendment.doc_id == doc_id)
    )
    amendment = amendment_result.scalar_one_or_none()
    if amendment is None:
        raise ValueError("Amendment not found")

    return amendment


def _format_comment(comment: AmendmentComment) -> CommentResponse:
    """
    Convert an AmendmentComment ORM instance to a CommentResponse schema.

    Parameters:
        comment: SQLAlchemy AmendmentComment instance (author relationship loaded).

    Returns:
        CommentResponse with author name/email resolved from the relationship.
    """
    author_name = None
    author_email = None
    if comment.author is not None:
        author_name = comment.author.name
        author_email = comment.author.email

    return CommentResponse(
        id=comment.id,
        amendment_id=comment.amendment_id,
        author_id=comment.author_id,
        author_name=author_name,
        author_email=author_email,
        body=comment.body,
        created_at=comment.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def list_comments(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
) -> CommentListResponse:
    """
    Return all comments on an amendment, ordered oldest-first.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user.
        slug: Organisation URL slug.
        doc_id: UUID of the parent document.
        amendment_id: UUID of the amendment.

    Returns:
        CommentListResponse with items and total.

    Raises:
        ValueError: If org/doc/amendment not found or user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    await _require_amendment(db, org, doc_id, amendment_id)

    result = await db.execute(
        select(AmendmentComment)
        .where(AmendmentComment.amendment_id == amendment_id)
        .order_by(AmendmentComment.created_at)
    )
    comments = result.scalars().all()

    # Eager-load authors in one query to avoid N+1
    author_ids = {c.author_id for c in comments if c.author_id}
    authors: dict[str, User] = {}
    if author_ids:
        author_result = await db.execute(
            select(User).where(User.id.in_(author_ids))
        )
        for user in author_result.scalars().all():
            authors[user.id] = user

    items = []
    for comment in comments:
        comment.author = authors.get(comment.author_id) if comment.author_id else None  # type: ignore[assignment]
        items.append(_format_comment(comment))

    return CommentListResponse(items=items, total=len(items))


async def create_comment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
    payload: CommentCreate,
) -> CommentResponse:
    """
    Post a new comment on an amendment.

    Any authenticated member may comment. Body is validated by the schema.
    After creation, an activity log entry is written and — if the amendment
    author is a different user who has notifications enabled and has not muted
    the organisation — a comment-notification email is dispatched.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user.
        slug: Organisation URL slug.
        doc_id: UUID of the parent document.
        amendment_id: UUID of the target amendment.
        payload: CommentCreate request body.

    Returns:
        CommentResponse for the newly created comment.

    Raises:
        ValueError: If org/doc/amendment not found or user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    amendment = await _require_amendment(db, org, doc_id, amendment_id)

    comment = AmendmentComment(
        id=str(uuid.uuid4()),
        amendment_id=amendment_id,
        author_id=current_user.id,
        body=payload.body,
    )
    db.add(comment)

    # Log activity (flush inside log_activity, committed below)
    await log_activity(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action=ActivityAction.amendment_commented,
        doc_id=doc_id,
        amendment_id=amendment_id,
    )

    await db.commit()
    await db.refresh(comment)

    # Attach author for formatting
    comment.author = current_user  # type: ignore[assignment]

    # --- Email notification -------------------------------------------------
    # Notify the amendment author if:
    #   1. The amendment has an author (not deleted/anonymous)
    #   2. The commenter is not the author themselves
    #   3. The author has global email notifications enabled
    #   4. The author has not muted notifications for this organisation
    if amendment.author_id and amendment.author_id != current_user.id:
        try:
            author_result = await db.execute(
                select(User).where(User.id == amendment.author_id)
            )
            amendment_author = author_result.scalar_one_or_none()

            if amendment_author and amendment_author.email_notifications_enabled:
                # Check org-level mute preference
                membership_result = await db.execute(
                    select(Membership).where(
                        Membership.user_id == amendment_author.id,
                        Membership.org_id == org.id,
                    )
                )
                author_membership = membership_result.scalar_one_or_none()

                if author_membership and not author_membership.notifications_muted:
                    # Fetch document title for the email
                    doc_result = await db.execute(
                        select(Document).where(Document.id == doc_id)
                    )
                    doc = doc_result.scalar_one_or_none()
                    doc_title = doc.title if doc else "Unknown document"

                    commenter_name = current_user.name or current_user.email

                    await send_amendment_commented_email(
                        recipient_email=amendment_author.email,
                        org_name=org.name,
                        doc_title=doc_title,
                        commenter_name=commenter_name,
                        doc_id=doc_id,
                        org_slug=org.slug,
                        section=amendment.section,
                        comment_body=payload.body,
                    )
        except Exception:
            logger.exception(
                "Failed to send comment notification for amendment %s", amendment_id
            )
    # -----------------------------------------------------------------------

    return _format_comment(comment)


async def delete_comment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
    comment_id: str,
) -> None:
    """
    Delete a comment. Allowed for the comment author or an org owner/admin.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user.
        slug: Organisation URL slug.
        doc_id: UUID of the parent document.
        amendment_id: UUID of the parent amendment.
        comment_id: UUID of the comment to delete.

    Returns:
        None (204 No Content).

    Raises:
        ValueError: If org/doc/amendment not found, user is not a member, the
            comment is not found, or the user is not authorised to delete it.
    """
    org, membership = await _require_membership(db, current_user, slug)
    await _require_amendment(db, org, doc_id, amendment_id)

    comment_result = await db.execute(
        select(AmendmentComment).where(
            AmendmentComment.id == comment_id,
            AmendmentComment.amendment_id == amendment_id,
        )
    )
    comment = comment_result.scalar_one_or_none()
    if comment is None:
        raise ValueError("Comment not found")

    is_author = comment.author_id == current_user.id
    is_moderator = membership.role in (MemberRole.owner, MemberRole.admin)
    if not is_author and not is_moderator:
        raise ValueError("Only the comment author or a moderator may delete this comment")

    await db.delete(comment)
