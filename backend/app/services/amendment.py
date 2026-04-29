"""
Amendment service — business logic for submitting and managing amendments.

All database interaction goes through this service so that the API routes
remain thin and testable in isolation.

Membership is always checked before any amendment operation.
Any authenticated member may submit an amendment.
Only owners and admins may change an amendment's status (accept/reject).
"""

import logging
import uuid

from sqlalchemy import func, select

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityAction
from app.models.amendment import Amendment, AmendmentStatus, AmendmentType
from app.models.amendment_comment import AmendmentComment
from app.models.amendment_reaction import AmendmentReaction, ReactionType
from app.models.document import Document, DocumentStatus
from app.models.membership import MemberRole, Membership
from app.models.organisation import OrgPlan, Organisation
from app.models.user import User
from app.schemas.amendment import (
    AmendmentCreate,
    AmendmentListResponse,
    AmendmentResponse,
    AmendmentStatusUpdate,
    ReactRequest,
    ReactionSummaryResponse,
)
from app.services.activity import log_activity
from app.utils.email import send_amendment_status_email, send_amendment_submitted_email

_REACTION_PLANS = {OrgPlan.organisation}

PAGE_SIZE = 20


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_amendment(
    a: Amendment,
    support_count: int = 0,
    oppose_count: int = 0,
    user_reaction: str | None = None,
    author_name: str | None = None,
    author_email: str | None = None,
    comment_count: int = 0,
) -> AmendmentResponse:
    """
    Convert an Amendment ORM instance to an AmendmentResponse schema.

    Parameters:
        a: SQLAlchemy Amendment instance.
        support_count: Number of support reactions on this amendment.
        oppose_count: Number of oppose reactions on this amendment.
        user_reaction: The current user's reaction type ('support'|'oppose'|None).
        author_name: Display name of the amendment author (optional).
        author_email: Email address of the amendment author (optional).
        comment_count: Number of thread comments on this amendment.

    Returns:
        AmendmentResponse with ISO-8601 created_at string, reaction data, author info,
        contributor identity, and comment count.
    """
    return AmendmentResponse(
        id=a.id,
        doc_id=a.doc_id,
        amendment_type=a.amendment_type.value,
        section=a.section,
        original_text=a.original_text,
        proposed_text=a.proposed_text,
        justification=a.justification,
        decision_reason=a.decision_reason,
        status=a.status.value,
        author_id=a.author_id,
        author_name=author_name,
        author_email=author_email,
        contributor_name=a.contributor_name,
        contributor_email=a.contributor_email,
        created_at=a.created_at.isoformat(),
        support_count=support_count,
        oppose_count=oppose_count,
        user_reaction=user_reaction,
        comment_count=comment_count,
    )


async def _get_author_info(
    db: AsyncSession,
    author_id: str | None,
) -> tuple[str | None, str | None]:
    """
    Fetch the display name and email for an amendment author.

    Parameters:
        db: Async SQLAlchemy session.
        author_id: UUID of the author user, or None.

    Returns:
        Tuple of (name, email), both None if author_id is None or user not found.
    """
    if not author_id:
        return None, None
    result = await db.execute(select(User).where(User.id == author_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None, None
    return user.name, user.email


async def _get_reaction_counts(
    db: AsyncSession,
    amendment_id: str,
    user_id: str,
) -> tuple[int, int, str | None]:
    """
    Fetch support count, oppose count, and the current user's reaction for an amendment.

    Parameters:
        db: Async SQLAlchemy session.
        amendment_id: UUID of the amendment.
        user_id: UUID of the current user.

    Returns:
        Tuple of (support_count, oppose_count, user_reaction).
    """
    counts_result = await db.execute(
        select(AmendmentReaction.reaction_type, func.count().label("n"))
        .where(AmendmentReaction.amendment_id == amendment_id)
        .group_by(AmendmentReaction.reaction_type)
    )
    support_count = 0
    oppose_count = 0
    for row in counts_result.all():
        if row.reaction_type == ReactionType.support:
            support_count = row.n
        elif row.reaction_type == ReactionType.oppose:
            oppose_count = row.n

    user_rx_result = await db.execute(
        select(AmendmentReaction).where(
            AmendmentReaction.amendment_id == amendment_id,
            AmendmentReaction.user_id == user_id,
        )
    )
    existing = user_rx_result.scalar_one_or_none()
    user_reaction = existing.reaction_type.value if existing else None

    return support_count, oppose_count, user_reaction


async def _require_membership(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> tuple[Organisation, Membership]:
    """
    Fetch an organisation by slug, verifying the caller is a member.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user making the request.
        slug: URL slug of the target organisation.

    Returns:
        Tuple of (Organisation, Membership) for the verified member.

    Raises:
        ValueError: If the org does not exist or the user is not a member.
                    Callers should map this to HTTP 404 to avoid disclosure.
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
    return row  # (Organisation, Membership)


async def _require_document(
    db: AsyncSession,
    org: Organisation,
    doc_id: str,
) -> Document:
    """
    Fetch a document by ID, verifying it belongs to the given organisation.

    Parameters:
        db: Async SQLAlchemy session.
        org: The Organisation the document must belong to.
        doc_id: UUID string of the target document.

    Returns:
        The matching Document ORM instance.

    Raises:
        ValueError: If the document is not found or does not belong to the org.
    """
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document '{doc_id}' not found.")
    return doc


def _require_write_access(membership: Membership) -> None:
    """
    Raise ValueError if the membership role is not owner or admin.

    Parameters:
        membership: The caller's Membership record for the organisation.

    Raises:
        ValueError: If the role is 'member' (read-only for status changes).
    """
    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise ValueError("Only owners and admins can accept or reject amendments.")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def create_amendment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    payload: AmendmentCreate,
) -> AmendmentResponse:
    """
    Submit a new amendment to a document.

    Any authenticated member of the organisation may submit an amendment.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user submitting the amendment.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.
        payload: Validated AmendmentCreate request body.

    Returns:
        AmendmentResponse for the newly created amendment.

    Raises:
        ValueError: If the org or document is not found, the user is not a member,
                    or the document is closed.
    """
    org, _ = await _require_membership(db, current_user, slug)
    doc = await _require_document(db, org, doc_id)

    if doc.status == DocumentStatus.closed:
        raise ValueError(
            f"Amendments cannot be submitted to closed documents "
            f"(current status: '{doc.status.value}')."
        )

    # Anchor check: skip for HTML bodies — selected text is plain text and won't
    # appear verbatim inside HTML markup.  Only enforce for plain-text bodies.
    if (
        payload.amendment_type == "text_change"
        and payload.original_text
        and doc.body
        and not doc.body.lstrip().startswith("<")
        and payload.original_text not in doc.body
    ):
        raise ValueError(
            "The original text was not found in the document. "
            "Please copy the exact passage you want to amend."
        )

    amendment = Amendment(
        doc_id=doc_id,
        amendment_type=AmendmentType(payload.amendment_type),
        section=payload.section,
        original_text=payload.original_text,
        proposed_text=payload.proposed_text,
        justification=payload.justification,
        author_id=current_user.id,
    )
    db.add(amendment)
    await db.flush()

    await log_activity(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action=ActivityAction.amendment_submitted,
        doc_id=doc_id,
        amendment_id=amendment.id,
    )

    # Notify owners and admins of the new amendment (fire-and-forget).
    # Skipped for users with email_notifications_enabled = False or notifications_muted = True for this org.
    managers_result = await db.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.org_id == org.id,
            Membership.role.in_([MemberRole.owner, MemberRole.admin]),
            User.id != current_user.id,  # don't notify the author if they are also an admin
            Membership.notifications_muted.is_(False),
        )
    )
    managers = managers_result.scalars().all()
    author_name = current_user.name or current_user.email
    for manager in managers:
        if manager.email_notifications_enabled:
            try:
                await send_amendment_submitted_email(
                    recipient_email=manager.email,
                    org_name=org.name,
                    doc_title=doc.title,
                    author_name=author_name,
                    doc_id=doc_id,
                    org_slug=slug,
                    section=payload.section,
                )
            except Exception:
                # Email delivery is best-effort; a Resend failure must not roll back
                # the successfully saved amendment.
                logger.exception(
                    "Failed to send amendment-submitted notification to %s", manager.email
                )

    return _format_amendment(
        amendment,
        author_name=current_user.name,
        author_email=current_user.email,
    )


async def list_amendments(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    page: int = 1,
) -> AmendmentListResponse:
    """
    List amendments for a document, paginated at 20 per page.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the list.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.
        page: 1-based page number (default 1).

    Returns:
        AmendmentListResponse containing items, total, page, and page_size.

    Raises:
        ValueError: If the org or document is not found or the user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    await _require_document(db, org, doc_id)

    offset = (page - 1) * PAGE_SIZE

    count_result = await db.execute(
        select(func.count()).where(Amendment.doc_id == doc_id)
    )
    total = count_result.scalar_one()

    amendments_result = await db.execute(
        select(Amendment)
        .where(Amendment.doc_id == doc_id)
        .order_by(Amendment.created_at.asc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    amendments = amendments_result.scalars().all()

    # Batch-fetch all reaction data for this page in exactly 2 queries instead of 2N.
    amendment_ids = [a.id for a in amendments]

    # Query 1: aggregate counts per (amendment_id, reaction_type)
    counts_result = await db.execute(
        select(
            AmendmentReaction.amendment_id,
            AmendmentReaction.reaction_type,
            func.count().label("n"),
        )
        .where(AmendmentReaction.amendment_id.in_(amendment_ids))
        .group_by(AmendmentReaction.amendment_id, AmendmentReaction.reaction_type)
    )
    support_map: dict[str, int] = {}
    oppose_map: dict[str, int] = {}
    for row in counts_result.all():
        if row.reaction_type == ReactionType.support:
            support_map[row.amendment_id] = row.n
        elif row.reaction_type == ReactionType.oppose:
            oppose_map[row.amendment_id] = row.n

    # Query 2: current user's own reactions across the page
    user_rx_result = await db.execute(
        select(AmendmentReaction).where(
            AmendmentReaction.amendment_id.in_(amendment_ids),
            AmendmentReaction.user_id == current_user.id,
        )
    )
    user_rx_map: dict[str, str] = {
        rx.amendment_id: rx.reaction_type.value for rx in user_rx_result.scalars().all()
    }

    # Query 3: batch-fetch author names and emails
    author_ids = list({a.author_id for a in amendments if a.author_id})
    author_map: dict[str, User] = {}
    if author_ids:
        authors_result = await db.execute(select(User).where(User.id.in_(author_ids)))
        for u in authors_result.scalars().all():
            author_map[u.id] = u

    # Query 4: batch-fetch comment counts per amendment
    comment_counts_result = await db.execute(
        select(AmendmentComment.amendment_id, func.count().label("n"))
        .where(AmendmentComment.amendment_id.in_(amendment_ids))
        .group_by(AmendmentComment.amendment_id)
    )
    comment_count_map: dict[str, int] = {row.amendment_id: row.n for row in comment_counts_result.all()}

    items = [
        _format_amendment(
            a,
            support_map.get(a.id, 0),
            oppose_map.get(a.id, 0),
            user_rx_map.get(a.id),
            author_name=author_map[a.author_id].name if a.author_id and a.author_id in author_map else None,
            author_email=author_map[a.author_id].email if a.author_id and a.author_id in author_map else None,
            comment_count=comment_count_map.get(a.id, 0),
        )
        for a in amendments
    ]

    return AmendmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


async def get_amendment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
) -> AmendmentResponse:
    """
    Fetch a single amendment by ID, verifying org membership and document ownership.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the amendment.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the owning document.
        amendment_id: UUID string of the target amendment.

    Returns:
        AmendmentResponse for the matching amendment.

    Raises:
        ValueError: If the org/document/amendment is not found or user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    await _require_document(db, org, doc_id)

    result = await db.execute(
        select(Amendment).where(
            Amendment.id == amendment_id,
            Amendment.doc_id == doc_id,
        )
    )
    amendment = result.scalar_one_or_none()
    if amendment is None:
        raise ValueError(f"Amendment '{amendment_id}' not found.")

    support, oppose, user_rx = await _get_reaction_counts(db, amendment.id, current_user.id)
    author_name, author_email = await _get_author_info(db, amendment.author_id)
    cc_result = await db.execute(
        select(func.count()).select_from(AmendmentComment).where(AmendmentComment.amendment_id == amendment.id)
    )
    comment_count = cc_result.scalar_one()
    return _format_amendment(amendment, support, oppose, user_rx, author_name, author_email, comment_count=comment_count)


async def update_amendment_status(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
    payload: AmendmentStatusUpdate,
) -> AmendmentResponse:
    """
    Accept or reject an amendment. Requires owner or admin role.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user changing the status.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the owning document.
        amendment_id: UUID string of the amendment to update.
        payload: Validated AmendmentStatusUpdate body (status: accepted | rejected).

    Returns:
        AmendmentResponse for the updated amendment.

    Raises:
        ValueError: If the org/document/amendment is not found, user is not a member,
                    user lacks write access (owner/admin required), or the amendment
                    is not in 'pending' status.
    """
    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)
    doc = await _require_document(db, org, doc_id)

    result = await db.execute(
        select(Amendment).where(
            Amendment.id == amendment_id,
            Amendment.doc_id == doc_id,
        )
    )
    amendment = result.scalar_one_or_none()
    if amendment is None:
        raise ValueError(f"Amendment '{amendment_id}' not found.")

    if amendment.status != AmendmentStatus.pending:
        raise ValueError(
            f"Only pending amendments can be accepted or rejected "
            f"(current status: '{amendment.status.value}')."
        )

    new_status = AmendmentStatus(payload.status)
    amendment.status = new_status
    if payload.decision_reason and payload.decision_reason.strip():
        amendment.decision_reason = payload.decision_reason.strip()
    await db.flush()

    # Determine the activity action and log it
    if new_status == AmendmentStatus.accepted:
        action = ActivityAction.amendment_accepted
    elif new_status == AmendmentStatus.rejected:
        action = ActivityAction.amendment_rejected
    else:
        action = None

    if action is not None:
        await log_activity(
            db,
            org_id=org.id,
            user_id=current_user.id,
            action=action,
            doc_id=doc_id,
            amendment_id=amendment.id,
        )

    # Fetch the author for the response and (conditionally) for the notification email.
    author_result = await db.execute(select(User).where(User.id == amendment.author_id))
    author = author_result.scalar_one_or_none()

    # Send notification email to the author (fire-and-forget — errors are logged).
    # Skipped if the author has opted out via email_notifications_enabled = False
    # or has muted notifications for this org via notifications_muted = True.
    if new_status in (AmendmentStatus.accepted, AmendmentStatus.rejected):
        if author and author.email_notifications_enabled:
            author_membership_result = await db.execute(
                select(Membership).where(
                    Membership.user_id == author.id,
                    Membership.org_id == org.id,
                )
            )
            author_membership = author_membership_result.scalar_one_or_none()
            if not (author_membership and author_membership.notifications_muted):
                await send_amendment_status_email(
                    recipient_email=author.email,
                    status=new_status.value,
                    org_name=org.name,
                    doc_title=doc.title,
                    doc_id=doc_id,
                    org_slug=slug,
                    section=amendment.section,
                    db=db,
                )

    support, oppose, user_rx = await _get_reaction_counts(db, amendment.id, current_user.id)
    return _format_amendment(
        amendment,
        support,
        oppose,
        user_rx,
        author_name=author.name if author else None,
        author_email=author.email if author else None,
    )


async def bulk_update_amendment_status(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    payload: "BulkAmendmentStatusUpdate",
) -> dict:
    """
    Accept or reject multiple pending amendments in a single transaction.

    Fetches all requested amendments, skips any that are not in 'pending' status
    (silently), and updates the rest.  Activity log entries are written for each
    updated amendment.  Notification emails are NOT sent for bulk actions to avoid
    inbox flooding; the decision_reason is still stored if provided.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user performing the bulk action (owner/admin).
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the owning document.
        payload: Validated BulkAmendmentStatusUpdate body.

    Returns:
        Dict with keys:
          updated_count — number of amendments actually changed.
          skipped_count — number of IDs that were not pending (and were skipped).

    Raises:
        ValueError: If the org/document is not found, the user is not a member,
                    or the user lacks write access (owner/admin required).
    """
    from app.schemas.amendment import BulkAmendmentStatusUpdate  # noqa: PLC0415

    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)
    doc = await _require_document(db, org, doc_id)

    new_status = AmendmentStatus(payload.status)
    reason = payload.decision_reason.strip() if payload.decision_reason and payload.decision_reason.strip() else None

    result = await db.execute(
        select(Amendment).where(
            Amendment.id.in_(payload.amendment_ids),
            Amendment.doc_id == doc_id,
        )
    )
    amendments = result.scalars().all()

    updated_count = 0
    skipped_count = len(payload.amendment_ids) - len(amendments)  # IDs not in this doc

    for amendment in amendments:
        if amendment.status != AmendmentStatus.pending:
            skipped_count += 1
            continue

        amendment.status = new_status
        if reason:
            amendment.decision_reason = reason
        updated_count += 1

        action = (
            ActivityAction.amendment_accepted
            if new_status == AmendmentStatus.accepted
            else ActivityAction.amendment_rejected
        )
        await log_activity(
            db,
            org_id=org.id,
            user_id=current_user.id,
            action=action,
            doc_id=doc_id,
            amendment_id=amendment.id,
        )

    await db.flush()
    return {"updated_count": updated_count, "skipped_count": skipped_count}


async def withdraw_amendment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
) -> None:
    """
    Soft-delete an amendment by setting its status to 'withdrawn'.

    Only the amendment's author may withdraw it, and only when it is still
    in 'pending' status.  The row is retained in the database so that history
    is preserved.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the withdrawal.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the owning document.
        amendment_id: UUID string of the amendment to withdraw.

    Returns:
        None (caller should respond with 204 No Content).

    Raises:
        ValueError: If the org/document/amendment is not found, the user is
                    not a member, the user is not the author, or the amendment
                    is not pending.
    """
    org, _ = await _require_membership(db, current_user, slug)
    await _require_document(db, org, doc_id)

    result = await db.execute(
        select(Amendment).where(
            Amendment.id == amendment_id,
            Amendment.doc_id == doc_id,
        )
    )
    amendment = result.scalar_one_or_none()
    if amendment is None:
        raise ValueError(f"Amendment '{amendment_id}' not found.")

    if amendment.author_id != current_user.id:
        raise ValueError("Only the amendment's author can withdraw it.")

    if amendment.status != AmendmentStatus.pending:
        raise ValueError("Only pending amendments can be withdrawn.")

    amendment.status = AmendmentStatus.withdrawn
    await db.flush()

    await log_activity(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action=ActivityAction.amendment_withdrawn,
        doc_id=doc_id,
        amendment_id=amendment.id,
    )


async def list_mine_amendments(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    page: int = 1,
) -> AmendmentListResponse:
    """
    List amendments submitted by the current user for a document, paginated at 20 per page.

    Any authenticated member may call this endpoint. Only amendments authored by
    the current user are returned.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting their own amendments.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.
        page: 1-based page number (default 1).

    Returns:
        AmendmentListResponse containing items, total, page, and page_size.

    Raises:
        ValueError: If the org or document is not found or the user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    await _require_document(db, org, doc_id)

    offset = (page - 1) * PAGE_SIZE

    count_result = await db.execute(
        select(func.count()).where(
            Amendment.doc_id == doc_id,
            Amendment.author_id == current_user.id,
        )
    )
    total = count_result.scalar_one()

    amendments_result = await db.execute(
        select(Amendment)
        .where(Amendment.doc_id == doc_id, Amendment.author_id == current_user.id)
        .order_by(Amendment.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    amendments = amendments_result.scalars().all()

    # Batch-fetch reaction data for this page in 2 queries.
    amendment_ids = [a.id for a in amendments]

    counts_result = await db.execute(
        select(
            AmendmentReaction.amendment_id,
            AmendmentReaction.reaction_type,
            func.count().label("n"),
        )
        .where(AmendmentReaction.amendment_id.in_(amendment_ids))
        .group_by(AmendmentReaction.amendment_id, AmendmentReaction.reaction_type)
    )
    support_map: dict[str, int] = {}
    oppose_map: dict[str, int] = {}
    for row in counts_result.all():
        if row.reaction_type == ReactionType.support:
            support_map[row.amendment_id] = row.n
        elif row.reaction_type == ReactionType.oppose:
            oppose_map[row.amendment_id] = row.n

    user_rx_result = await db.execute(
        select(AmendmentReaction).where(
            AmendmentReaction.amendment_id.in_(amendment_ids),
            AmendmentReaction.user_id == current_user.id,
        )
    )
    user_rx_map: dict[str, str] = {
        rx.amendment_id: rx.reaction_type.value for rx in user_rx_result.scalars().all()
    }

    # Batch-fetch author names and emails for this page
    mine_author_ids = list({a.author_id for a in amendments if a.author_id})
    mine_author_map: dict[str, User] = {}
    if mine_author_ids:
        mine_authors_result = await db.execute(select(User).where(User.id.in_(mine_author_ids)))
        for u in mine_authors_result.scalars().all():
            mine_author_map[u.id] = u

    items = [
        _format_amendment(
            a,
            support_map.get(a.id, 0),
            oppose_map.get(a.id, 0),
            user_rx_map.get(a.id),
            author_name=mine_author_map[a.author_id].name if a.author_id and a.author_id in mine_author_map else None,
            author_email=mine_author_map[a.author_id].email if a.author_id and a.author_id in mine_author_map else None,
        )
        for a in amendments
    ]

    return AmendmentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


async def get_reaction_summary(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
) -> ReactionSummaryResponse:
    """
    Return aggregated reaction counts across all pending amendments for a document.

    Plan gating: only the Organisation plan may access this summary.
    Access control: only owners and admins may call this endpoint (in addition to
    the plan gate). Members would not be able to access this through the UI, but
    enforcing it here prevents direct API calls from exposing sentiment data.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the summary.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.

    Returns:
        ReactionSummaryResponse with total_pending, support_count, and oppose_count.

    Raises:
        ValueError: If the org/document is not found, the user is not a member,
                    the caller is not an owner/admin, or the organisation is not
                    on the Organisation plan.
    """
    org, membership = await _require_membership(db, current_user, slug)

    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise ValueError("Only owners and admins can view the reaction summary.")

    if org.plan not in _REACTION_PLANS:
        raise ValueError("Organisation plan only.")

    await _require_document(db, org, doc_id)

    # Collect IDs of all pending amendments for this document
    pending_result = await db.execute(
        select(Amendment.id).where(
            Amendment.doc_id == doc_id,
            Amendment.status == AmendmentStatus.pending,
        )
    )
    pending_ids = [row[0] for row in pending_result.all()]
    total_pending = len(pending_ids)

    if total_pending == 0:
        return ReactionSummaryResponse(total_pending=0, support_count=0, oppose_count=0)

    # Sum reactions across all pending amendments in one query
    counts_result = await db.execute(
        select(AmendmentReaction.reaction_type, func.count().label("n"))
        .where(AmendmentReaction.amendment_id.in_(pending_ids))
        .group_by(AmendmentReaction.reaction_type)
    )
    support_count = 0
    oppose_count = 0
    for row in counts_result.all():
        if row.reaction_type == ReactionType.support:
            support_count = row.n
        elif row.reaction_type == ReactionType.oppose:
            oppose_count = row.n

    return ReactionSummaryResponse(
        total_pending=total_pending,
        support_count=support_count,
        oppose_count=oppose_count,
    )


async def react_to_amendment(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    amendment_id: str,
    payload: ReactRequest,
) -> AmendmentResponse:
    """
    Record, update, or cancel a member's reaction (support / oppose) on an amendment.

    Toggle semantics:
      - If the user has no reaction → create it.
      - If the user already has the same reaction type → delete it (cancel).
      - If the user has the opposite reaction type → update it.

    Plan gating: only the Organisation plan may use reactions.
    Any authenticated member may react; moderation (accept/reject) is not required.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user reacting.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the owning document.
        amendment_id: UUID string of the target amendment.
        payload: ReactRequest body (type: 'support' | 'oppose').

    Returns:
        AmendmentResponse with updated support_count, oppose_count, user_reaction.

    Raises:
        ValueError: If the org or document is not found, the user is not a member,
                    the plan is not Organisation, or the amendment is not found.
    """
    org, _ = await _require_membership(db, current_user, slug)

    if org.plan not in _REACTION_PLANS:
        raise ValueError("Reactions are only available on the Organisation plan.")

    await _require_document(db, org, doc_id)

    result = await db.execute(
        select(Amendment).where(
            Amendment.id == amendment_id,
            Amendment.doc_id == doc_id,
        )
    )
    amendment = result.scalar_one_or_none()
    if amendment is None:
        raise ValueError(f"Amendment '{amendment_id}' not found.")

    requested_type = ReactionType(payload.type)

    # Check for an existing reaction from this user
    existing_result = await db.execute(
        select(AmendmentReaction).where(
            AmendmentReaction.amendment_id == amendment_id,
            AmendmentReaction.user_id == current_user.id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is None:
        # No reaction yet — create one
        reaction = AmendmentReaction(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            amendment_id=amendment_id,
            reaction_type=requested_type,
        )
        db.add(reaction)
    elif existing.reaction_type == requested_type:
        # Same type — toggle off (cancel)
        await db.delete(existing)
    else:
        # Different type — replace
        existing.reaction_type = requested_type

    await db.flush()

    support, oppose, user_rx = await _get_reaction_counts(db, amendment_id, current_user.id)
    author_name, author_email = await _get_author_info(db, amendment.author_id)
    return _format_amendment(amendment, support, oppose, user_rx, author_name, author_email)
