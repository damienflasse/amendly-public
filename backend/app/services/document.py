"""
Document service — business logic for creating and querying documents.

All database interaction goes through this service so that the API routes
remain thin and testable in isolation.

Membership is always checked before any document operation:
non-members receive a ValueError that the route maps to 404.
Only owners and admins may mutate (create / update) documents.
"""

import html
import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityAction
from app.models.amendment import Amendment, AmendmentStatus
from app.models.document import Document, DocumentStatus
from app.models.membership import MemberRole, Membership
from app.models.organisation import Organisation
from app.models.user import User
from app.services.activity import log_activity
from app.services.plan_config import get_document_limit_for_plan
from app.utils.diff import compute_diff
from app.schemas.document import (
    ConsolidatedResponse,
    DiffToken,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
    ReviewAmendmentItem,
    ReviewResponse,
    SectionUpdate,
)

PAGE_SIZE = 20
CONTRIBUTOR_LINK_STATUS_ACTIVE = "active"
CONTRIBUTOR_LINK_STATUS_EXPIRED = "expired"
CONTRIBUTOR_LINK_STATUS_REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class _ReviewHtmlTextExtractor(HTMLParser):
    """Convert stored rich-text HTML into readable plain text for diffing."""

    _BLOCK_TAGS = {"p", "div", "h2", "h3", "h4", "blockquote", "li"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag == "br":
            self._parts.append("\n")
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag == "hr":
            self._parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        text = html.unescape("".join(self._parts))
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()


def _body_to_review_text(body: str | None) -> str:
    """Return a readable text version of a stored document body for review diffs."""
    if not body:
        return ""
    if "<" not in body:
        return body.strip()

    parser = _ReviewHtmlTextExtractor()
    parser.feed(body)
    parser.close()
    text = parser.get_text()
    return text or re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


def _coerce_utc(dt: datetime | None) -> datetime | None:
    """Normalise DB datetimes to aware UTC values for safe comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_contributor_link_status(
    doc: Document,
    *,
    now: datetime | None = None,
) -> str:
    """Return the contributor-link business state for a document."""
    if not doc.contributor_token:
        return CONTRIBUTOR_LINK_STATUS_REVOKED
    expires_at = _coerce_utc(doc.contributor_token_expires_at)
    if expires_at is not None and expires_at <= (now or datetime.now(UTC)):
        return CONTRIBUTOR_LINK_STATUS_EXPIRED
    return CONTRIBUTOR_LINK_STATUS_ACTIVE


def _format_doc(doc: Document, pending_count: int = 0) -> DocumentResponse:
    """
    Convert a Document ORM instance to a DocumentResponse schema.

    Parameters:
        doc: SQLAlchemy Document instance.
        pending_count: Number of pending amendments for this document (default 0).
            Populated by list_documents via a subquery; omitted for single-doc fetches.

    Returns:
        DocumentResponse with ISO-8601 created_at string and pending_count.
    """
    return DocumentResponse(
        id=doc.id,
        org_id=doc.org_id,
        title=doc.title,
        body=doc.body,
        status=doc.status.value,
        created_at=_coerce_utc(doc.created_at).isoformat(),
        pending_count=pending_count,
        contributor_token=doc.contributor_token,
        contributor_token_created_at=(
            _coerce_utc(doc.contributor_token_created_at).isoformat()
            if doc.contributor_token_created_at
            else None
        ),
        contributor_token_expires_at=(
            _coerce_utc(doc.contributor_token_expires_at).isoformat()
            if doc.contributor_token_expires_at
            else None
        ),
        contributor_link_status=get_contributor_link_status(doc),
    )


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


def _require_write_access(membership: Membership) -> None:
    """
    Raise ValueError if the membership role is not owner or admin.

    Parameters:
        membership: The caller's Membership record for the organisation.

    Raises:
        ValueError: If the role is 'member' (read-only).
    """
    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise ValueError("Only owners and admins can create or update documents.")


async def _get_org_document(db: AsyncSession, org_id: str, doc_id: str) -> Document:
    """
    Fetch a document scoped to a specific organisation.

    Parameters:
        db: Async SQLAlchemy session.
        org_id: UUID of the owning organisation.
        doc_id: UUID of the target document.

    Returns:
        The matching Document ORM instance.

    Raises:
        ValueError: If the document does not exist in the organisation.
    """
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document '{doc_id}' not found.")
    return doc


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def create_document(
    db: AsyncSession,
    current_user: User,
    slug: str,
    payload: DocumentCreate,
) -> DocumentResponse:
    """
    Create a new document inside an organisation.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user creating the document.
        slug: URL slug of the owning organisation.
        payload: Validated DocumentCreate request body (title, optional body).

    Returns:
        DocumentResponse for the newly created document.

    Raises:
        ValueError: If the org is not found, user is not a member, or user
                    lacks write access (owner/admin required).
    """
    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)

    # Enforce per-plan active-document cap (NULL = unlimited).
    # Only draft and open documents count — closed ones are finalised and
    # should not block creation of new documents.
    doc_limit = await get_document_limit_for_plan(db, org.plan.value)
    if doc_limit is not None:
        count_result = await db.execute(
            select(func.count()).where(
                Document.org_id == org.id,
                Document.status != DocumentStatus.closed,
            )
        )
        current_count = count_result.scalar_one()
        if current_count >= doc_limit:
            raise ValueError(
                f"Your plan ('{org.plan.value}') is limited to {doc_limit} active document(s). "
                "Upgrade your plan to create more documents."
            )

    doc = Document(org_id=org.id, title=payload.title, body=payload.body)
    db.add(doc)
    await db.flush()

    await log_activity(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action=ActivityAction.document_created,
        doc_id=doc.id,
    )

    return _format_doc(doc)


async def list_documents(
    db: AsyncSession,
    current_user: User,
    slug: str,
    page: int = 1,
) -> DocumentListResponse:
    """
    List documents for an organisation, paginated at 20 per page.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the list.
        slug: URL slug of the target organisation.
        page: 1-based page number (default 1).

    Returns:
        DocumentListResponse containing items, total, page, and page_size.

    Raises:
        ValueError: If the org is not found or the user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)

    offset = (page - 1) * PAGE_SIZE

    count_result = await db.execute(
        select(func.count()).where(Document.org_id == org.id)
    )
    total = count_result.scalar_one()

    # Scalar subquery: count of pending amendments per document row
    pending_sq = (
        select(func.count(Amendment.id))
        .where(
            Amendment.doc_id == Document.id,
            Amendment.status == AmendmentStatus.pending,
        )
        .correlate(Document)
        .scalar_subquery()
    )

    docs_result = await db.execute(
        select(Document, pending_sq.label("pending_count"))
        .where(Document.org_id == org.id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    rows = docs_result.all()

    return DocumentListResponse(
        items=[_format_doc(doc, pending_count=pc) for doc, pc in rows],
        total=total,
        page=page,
        page_size=PAGE_SIZE,
    )


async def get_document(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
) -> DocumentResponse:
    """
    Fetch a single document by ID, verifying org membership.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the document.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.

    Returns:
        DocumentResponse for the matching document.

    Raises:
        ValueError: If the org/doc is not found or the user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    doc = await _get_org_document(db, org.id, doc_id)
    return _format_doc(doc)


async def update_document(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    payload: DocumentUpdate,
) -> DocumentResponse:
    """
    Update a document's title and/or body. Requires owner or admin role.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user updating the document.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the document to update.
        payload: Validated DocumentUpdate body (title and/or body, both optional).

    Returns:
        DocumentResponse for the updated document.

    Raises:
        ValueError: If the org/doc is not found, user is not a member,
                    or user lacks write access (owner/admin required).
    """
    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)
    doc = await _get_org_document(db, org.id, doc_id)

    if payload.title is not None:
        doc.title = payload.title
    if payload.body is not None:
        if doc.status != DocumentStatus.draft:
            raise ValueError(
                "The document body can only be edited while the document is in draft status. "
                "Use the sections endpoint to update section headings on a closed document."
            )
        doc.body = payload.body

    await db.flush()
    return _format_doc(doc)


async def update_document_sections(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    payload: SectionUpdate,
) -> DocumentResponse:
    """
    Update only the section structure (h2/h3 headings) of a document body.

    Permitted when the document is in *draft* or *closed* status.
    Rejected when status is *open* — changing section structure while amendments
    are being collected would silently break the section-to-amendment mapping.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user updating the document.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the document to update.
        payload: SectionUpdate body containing the full updated HTML body.

    Returns:
        DocumentResponse for the updated document.

    Raises:
        ValueError: If the org/doc is not found, user is not a member,
                    user lacks write access, or the document is currently open.
    """
    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)
    doc = await _get_org_document(db, org.id, doc_id)

    if doc.status == DocumentStatus.open:
        raise ValueError(
            "Section headings cannot be modified while the document is open for amendments. "
            "Close the document first, then edit its sections."
        )

    if payload.title is not None:
        doc.title = payload.title
    doc.body = payload.body
    await db.flush()
    return _format_doc(doc)


async def get_consolidated(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
) -> ConsolidatedResponse:
    """
    Return the document body with all accepted amendments applied in order.

    Accepted amendments are applied sequentially (oldest first). Each amendment
    replaces the first occurrence of its original_text with its proposed_text.
    If an amendment's original_text is no longer present in the current body
    (because it was displaced by an earlier amendment), it is skipped gracefully
    rather than raising an error.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the consolidated view.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.

    Returns:
        ConsolidatedResponse with title, body_with_amendments_applied,
        and the count of applied amendments.

    Raises:
        ValueError: If the org/doc is not found or the user is not a member.
    """
    org, _ = await _require_membership(db, current_user, slug)
    doc = await _get_org_document(db, org.id, doc_id)

    # Fetch all accepted amendments ordered by creation time (oldest first)
    amendments_result = await db.execute(
        select(Amendment)
        .where(
            Amendment.doc_id == doc_id,
            Amendment.status == AmendmentStatus.accepted,
        )
        .order_by(Amendment.created_at.asc())
    )
    accepted_amendments = amendments_result.scalars().all()

    body = doc.body or ""
    applied = 0

    for amendment in accepted_amendments:
        original = amendment.original_text
        proposed = amendment.proposed_text
        if original in body:
            body = body.replace(original, proposed, 1)
            applied += 1

    return ConsolidatedResponse(
        title=doc.title,
        body_with_amendments_applied=body,
        amendments_applied=applied,
    )


async def update_document_status(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
    payload: DocumentStatusUpdate,
) -> DocumentResponse:
    """
    Change a document's lifecycle status. Requires owner or admin role.

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the status change.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the document to update.
        payload: Validated DocumentStatusUpdate body (status: draft | open | closed).

    Returns:
        DocumentResponse for the updated document.

    Raises:
        ValueError: If the org/doc is not found, user is not a member,
                    or user lacks write access (owner/admin required).
    """
    org, membership = await _require_membership(db, current_user, slug)
    _require_write_access(membership)
    doc = await _get_org_document(db, org.id, doc_id)
    doc.status = DocumentStatus(payload.status)
    await db.flush()

    await log_activity(
        db,
        org_id=org.id,
        user_id=current_user.id,
        action=ActivityAction.status_changed,
        doc_id=doc.id,
    )

    return _format_doc(doc)


async def delete_documents(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_ids: list[str],
) -> int:
    """
    Permanently delete a batch of documents by ID. Owner-only operation.

    All provided doc_ids must belong to the given organisation; any that do
    not exist or belong to a different org are silently skipped (idempotent).

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the deletion.
        slug: URL slug of the owning organisation.
        doc_ids: List of document UUID strings to delete.

    Returns:
        Number of documents actually deleted.

    Raises:
        ValueError: If the org is not found, user is not a member,
                    or user is not the owner.
    """
    org, membership = await _require_membership(db, current_user, slug)
    if membership.role != MemberRole.owner:
        raise ValueError("Only the organisation owner can delete documents.")

    if not doc_ids:
        return 0

    result = await db.execute(
        select(Document).where(
            Document.org_id == org.id,
            Document.id.in_(doc_ids),
        )
    )
    docs = result.scalars().all()

    for doc in docs:
        await db.delete(doc)

    await db.flush()
    return len(docs)


async def get_review(
    db: AsyncSession,
    current_user: User,
    slug: str,
    doc_id: str,
) -> ReviewResponse:
    """
    Return the full review payload for a document prior to export.

    Computes:
    - The original document body.
    - The consolidated body (accepted amendments applied in chronological order).
    - A word-level diff between the two bodies (full-document diff).
    - Counts of amendments by status (accepted / pending / rejected / withdrawn).
    - The ordered list of accepted amendments, each with its own word-level diff,
      author name, section, and justification.

    Available to all organisation members (not restricted to owner/admin).

    Parameters:
        db: Async SQLAlchemy session.
        current_user: The authenticated user requesting the review.
        slug: URL slug of the owning organisation.
        doc_id: UUID string of the target document.

    Returns:
        ReviewResponse containing all review data.

    Raises:
        ValueError: If the org/doc is not found or the user is not a member.
    """
    from app.models.amendment import AmendmentType

    org, _ = await _require_membership(db, current_user, slug)

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document '{doc_id}' not found.")

    original_body = doc.body or ""

    # Fetch all amendments (all statuses) for this document with author via LEFT JOIN.
    # LEFT OUTER JOIN is required because author_id can be NULL (ON DELETE SET NULL)
    # — an INNER JOIN would silently drop amendments whose author was deleted.
    all_amendments_result = await db.execute(
        select(Amendment, User)
        .outerjoin(User, User.id == Amendment.author_id)
        .where(Amendment.doc_id == doc_id)
        .order_by(Amendment.created_at.asc())
    )
    all_rows = all_amendments_result.all()

    # Count by status
    count_accepted = sum(1 for a, _ in all_rows if a.status == AmendmentStatus.accepted)
    count_pending = sum(1 for a, _ in all_rows if a.status == AmendmentStatus.pending)
    count_rejected = sum(1 for a, _ in all_rows if a.status == AmendmentStatus.rejected)
    count_withdrawn = sum(1 for a, _ in all_rows if a.status == AmendmentStatus.withdrawn)

    # Build consolidated body and collect accepted amendment items
    body = original_body
    accepted_items: list[ReviewAmendmentItem] = []

    for amendment, author in all_rows:
        if amendment.status != AmendmentStatus.accepted:
            continue

        # Apply text_change amendments to build consolidated body
        if (
            amendment.amendment_type == AmendmentType.text_change
            and amendment.original_text
            and amendment.original_text in body
        ):
            body = body.replace(amendment.original_text, amendment.proposed_text or "", 1)

        # Compute per-amendment diff tokens
        if amendment.amendment_type == AmendmentType.text_change:
            raw_tokens = compute_diff(
                amendment.original_text or "",
                amendment.proposed_text or "",
            )
        else:
            raw_tokens = []

        # Resolve author display name. If the author account was GDPR-erased (soft-deleted),
        # show a neutral placeholder instead of the anonymised email (deleted-{uuid}@deleted.invalid).
        if author is None or author.is_deleted:
            author_name = "[deleted user]"
        else:
            author_name = author.name or author.email

        accepted_items.append(
            ReviewAmendmentItem(
                id=amendment.id,
                section=amendment.section,
                original_text=amendment.original_text,
                proposed_text=amendment.proposed_text,
                justification=amendment.justification,
                author_name=author_name,
                created_at=amendment.created_at.isoformat(),
                diff_tokens=[DiffToken(text=t["text"], type=t["type"]) for t in raw_tokens],
            )
        )

    consolidated_body = body

    # Compute the review diff from readable text, not stored HTML markup.
    full_diff_raw = compute_diff(
        _body_to_review_text(original_body),
        _body_to_review_text(consolidated_body),
    )
    full_diff_tokens = [DiffToken(text=t["text"], type=t["type"]) for t in full_diff_raw]

    return ReviewResponse(
        title=doc.title,
        original_body=original_body,
        consolidated_body=consolidated_body,
        full_diff_tokens=full_diff_tokens,
        count_accepted=count_accepted,
        count_pending=count_pending,
        count_rejected=count_rejected,
        count_withdrawn=count_withdrawn,
        accepted_amendments=accepted_items,
    )
