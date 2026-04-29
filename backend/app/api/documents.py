"""
Document API routes — scoped under /api/organisations/{slug}/documents.

Endpoints:
  POST /api/organisations/{slug}/documents                   — create a document (owner/admin only)
  GET  /api/organisations/{slug}/documents                   — list documents (paginated, 20/page)
  GET  /api/organisations/{slug}/documents/{doc_id}          — fetch one document
  PUT  /api/organisations/{slug}/documents/{doc_id}          — update title/body (owner/admin only)
  GET  /api/organisations/{slug}/documents/{doc_id}/export   — export consolidated document (owner/admin only)
                                                               ?format=docx|pdf|txt|csv|json

All endpoints enforce membership: non-members receive 404 to avoid disclosing
the existence of private organisations and their documents.
"""

import io
import logging
import re
import secrets
import zipfile
from datetime import UTC, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.amendment import Amendment, AmendmentStatus
from app.models.document import Document
from app.models.membership import MemberRole
from app.models.organisation import OrgPlan
from app.models.user import User
from app.schemas.document import (
    ConsolidatedResponse,
    ContributorTokenResponse,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
    ReviewResponse,
    SectionUpdate,
)
from app.services.document import (
    CONTRIBUTOR_LINK_STATUS_REVOKED,
    _require_membership,
    create_document,
    delete_documents,
    get_consolidated,
    get_document,
    get_review,
    list_documents,
    update_document,
    update_document_sections,
    update_document_status,
)
from app.utils.docx_import import docx_bytes_to_html
from app.utils.pdf_import import pdf_bytes_to_import_result
from app.utils.export import export_csv, export_docx, export_json, export_pdf, export_txt

router = APIRouter(
    prefix="/api/organisations/{slug}/documents",
    tags=["documents"],
)

MAX_IMPORT_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


async def _require_import_membership(
    db: AsyncSession,
    current_user: User,
    slug: str,
) -> None:
    """
    Ensure the caller can access document import helpers for the organisation.

    Parameters:
        db: Injected async DB session.
        current_user: Authenticated caller.
        slug: URL slug of the target organisation.

    Raises:
        HTTPException 404: If the organisation is not found or the user is not a member.
    """
    try:
        await _require_membership(db, current_user, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


async def _read_validated_import_file(
    file: UploadFile,
    *,
    expected_prefix: bytes,
    invalid_detail: str,
) -> bytes:
    """
    Read an uploaded import file and validate its size and magic bytes.

    Parameters:
        file: Uploaded file received by FastAPI.
        expected_prefix: File signature prefix expected at the start of the payload.
        invalid_detail: Error message returned when the signature is invalid.

    Returns:
        Raw file bytes.

    Raises:
        HTTPException 400: If the file is too large or does not match the expected format.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMPORT_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier trop volumineux. Taille maximale : 10 Mo.",
        )
    if file_bytes[: len(expected_prefix)] != expected_prefix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_detail)
    return file_bytes


def _count_import_characters(html: str, title: str | None = None) -> int:
    """
    Estimate the visible character count of an imported document.

    Parameters:
        html: Extracted HTML body.
        title: Optional extracted title prepended to the count.

    Returns:
        Character count of the plain-text representation.
    """
    plain = re.sub(r"<[^>]+>", "", html)
    if title:
        plain = f"{title}{plain}"
    return len(plain)


class ExtractDocxResponse(BaseModel):
    """Response body for the DOCX extraction endpoint.

    Attributes:
        html: Extracted document content as clean HTML,
            ready to be loaded into a TipTap editor.
        char_count: Approximate character count of the extracted text.
        warnings: List of advisory strings (e.g. 'tables_ignored').
    """

    html: str
    char_count: int
    warnings: list[str] = []


class ExtractPdfResponse(BaseModel):
    """Response body for the PDF extraction endpoint.

    Attributes:
        html: Extracted document content as basic HTML,
            ready to be loaded into a TipTap editor.
        title: Extracted document title when one can be inferred reliably.
        char_count: Approximate character count of the extracted text.
        warnings: List of advisory strings (e.g. 'tables_ignored').
    """

    html: str
    title: str | None = None
    char_count: int
    warnings: list[str] = []


@router.post("/extract-docx", response_model=ExtractDocxResponse)
async def extract_docx(
    slug: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractDocxResponse:
    """
    Extract text content from an uploaded .docx file and return it as HTML.

    The extracted HTML preserves headings, paragraphs, bold/italic runs, and
    bullet/numbered lists.  The result can be loaded directly into a TipTap
    editor (StarterKit).  The document body is NOT saved — the caller must
    issue a subsequent PUT …/documents/{doc_id} to persist the content.

    Requires the caller to be a member (any role) of the specified organisation.
    The slug is validated purely for membership gating; no specific document is
    required at extraction time.

    Parameters:
        slug: URL slug of the owning organisation (membership check only).
        file: Uploaded .docx file (multipart/form-data).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        ExtractDocxResponse with the HTML string and character count.

    Raises:
        HTTPException 400: If the file cannot be parsed or exceeds the size limit.
        HTTPException 404: If the organisation is not found or the user is not a member.
    """
    await _require_import_membership(db, current_user, slug)
    file_bytes = await _read_validated_import_file(
        file,
        expected_prefix=b"PK",
        invalid_detail="Le fichier ne semble pas être un document Word (.docx) valide.",
    )

    try:
        extracted = docx_bytes_to_html(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    char_count = _count_import_characters(extracted.html)

    logger.info(
        "document_import",
        extra={
            "event": "docx_import",
            "org_slug": slug,
            "user_id": str(current_user.id),
            "file_size_bytes": len(file_bytes),
            "char_count": char_count,
            "warnings": extracted.warnings,
        },
    )

    return ExtractDocxResponse(
        html=extracted.html,
        char_count=char_count,
        warnings=extracted.warnings,
    )


@router.post("/extract-pdf", response_model=ExtractPdfResponse)
async def extract_pdf(
    slug: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractPdfResponse:
    """
    Extract text content from an uploaded .pdf file and return it as HTML.

    The extracted result preserves simple paragraph structure, page breaks,
    and may infer a title from the PDF metadata or first heading-like block.
    The document body is NOT saved — the caller must issue a subsequent write
    request to persist the content.

    Parameters:
        slug: URL slug of the owning organisation (membership check only).
        file: Uploaded .pdf file (multipart/form-data).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        ExtractPdfResponse with the HTML string and character count.

    Raises:
        HTTPException 400: If the file cannot be parsed or exceeds the size limit.
        HTTPException 404: If the organisation is not found or the user is not a member.
    """
    await _require_import_membership(db, current_user, slug)
    file_bytes = await _read_validated_import_file(
        file,
        expected_prefix=b"%PDF",
        invalid_detail="Le fichier ne semble pas être un PDF valide.",
    )

    try:
        extracted = pdf_bytes_to_import_result(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    char_count = _count_import_characters(extracted.html, extracted.title)

    logger.info(
        "document_import",
        extra={
            "event": "pdf_import",
            "org_slug": slug,
            "user_id": str(current_user.id),
            "file_size_bytes": len(file_bytes),
            "char_count": char_count,
            "title_detected": extracted.title is not None,
            "warnings": extracted.warnings,
        },
    )

    return ExtractPdfResponse(
        html=extracted.html,
        title=extracted.title,
        char_count=char_count,
        warnings=extracted.warnings,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def post_document(
    slug: str,
    body: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Create a new document inside the specified organisation.

    Only owners and admins may create documents. Non-members receive 404.

    Parameters:
        slug: URL slug of the owning organisation.
        body: DocumentCreate request body (title required, body optional).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DocumentResponse for the newly created document (201 Created).

    Raises:
        HTTPException 403: If the user is a member but lacks write access.
        HTTPException 404: If the org does not exist or the user is not a member.
    """
    try:
        return await create_document(db=db, current_user=current_user, slug=slug, payload=body)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg or "Free plan" in msg or "Upgrade your plan" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.get("", response_model=DocumentListResponse)
async def get_documents(
    slug: str,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """
    List documents for an organisation, paginated at 20 per page.

    Non-members receive 404 to avoid disclosing private org contents.

    Parameters:
        slug: URL slug of the target organisation.
        page: Page number (1-based, default 1).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DocumentListResponse with items, total, page, and page_size.

    Raises:
        HTTPException 404: If the org does not exist or the user is not a member.
    """
    try:
        return await list_documents(db=db, current_user=current_user, slug=slug, page=page)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document_by_id(
    slug: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Fetch a single document by its ID.

    Returns 404 both when the document does not exist and when the user is
    not a member of the owning organisation.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DocumentResponse for the matching document.

    Raises:
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        return await get_document(db=db, current_user=current_user, slug=slug, doc_id=doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{doc_id}/consolidated", response_model=ConsolidatedResponse)
async def get_consolidated_document(
    slug: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsolidatedResponse:
    """
    Return the document body with all accepted amendments applied in order.

    Amendments are applied oldest-first, each replacing the first occurrence of
    original_text with proposed_text in the current body. Amendments whose
    original_text is no longer present (displaced by an earlier amendment) are
    skipped gracefully. Available to all organisation members.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        ConsolidatedResponse with title, body_with_amendments_applied, and
        the count of amendments that were successfully applied.

    Raises:
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        return await get_consolidated(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{doc_id}/review", response_model=ReviewResponse)
async def get_document_review(
    slug: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """
    Return the full review payload for a document prior to export.

    Provides a comprehensive before-export summary including:
    - The original document body and the consolidated body (accepted amendments applied).
    - A word-level diff between the two bodies.
    - Counts of amendments grouped by status (accepted / pending / rejected / withdrawn).
    - The ordered list of accepted amendments, each with its own diff tokens, author
      name, section, and justification.

    Available to all organisation members (not restricted to owner/admin).

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the target document.
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        ReviewResponse with the full review payload.

    Raises:
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        return await get_review(db=db, current_user=current_user, slug=slug, doc_id=doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{doc_id}", response_model=DocumentResponse)
async def put_document(
    slug: str,
    doc_id: str,
    body: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Update a document's title and/or body. Requires owner or admin role.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the document to update.
        body: DocumentUpdate request body (title and/or body, both optional).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DocumentResponse with the updated fields.

    Raises:
        HTTPException 403: If the user lacks write access (member role).
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        return await update_document(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, payload=body
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg or "can only be edited" in msg or "sections endpoint" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.put("/{doc_id}/status", response_model=DocumentResponse)
async def put_document_status(
    slug: str,
    doc_id: str,
    body: DocumentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Change a document's lifecycle status (draft → open → closed).

    Only owners and admins may change document status.

    Parameters:
        slug: URL slug of the owning organisation.
        doc_id: UUID of the document to update.
        body: DocumentStatusUpdate request body (status: draft | open | closed).
        current_user: Injected via the get_current_user dependency.
        db: Injected async DB session.

    Returns:
        DocumentResponse with the updated status field.

    Raises:
        HTTPException 403: If the user lacks write access (member role).
        HTTPException 404: If the org/doc is not found or the user is not a member.
        HTTPException 422: If the status value is not one of draft | open | closed.
    """
    try:
        return await update_document_status(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, payload=body
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


@router.patch("/{doc_id}/sections", response_model=DocumentResponse)
async def patch_document_sections(
    slug: str,
    doc_id: str,
    body: SectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Update the section structure (h2/h3 headings) of a document body.

    Permitted when the document is in draft or closed status.
    Rejected when status is open — editing structure while amendments are being
    collected would silently break the section-to-amendment mapping.

    Requires owner or admin role.

    Parameters:
        slug:         URL slug of the owning organisation.
        doc_id:       UUID of the document to update.
        body:         SectionUpdate body containing the full updated HTML and
                      an optional title update.
        current_user: Injected via the get_current_user dependency.
        db:           Injected async DB session.

    Returns:
        DocumentResponse with the updated body.

    Raises:
        HTTPException 403: If the caller is a member (not owner/admin) or the
            document is currently open for amendments.
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        return await update_document_sections(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id, payload=body
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only owners" in msg or "cannot be modified" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc


# ---------------------------------------------------------------------------
# Batch delete
# ---------------------------------------------------------------------------


class BatchDeleteRequest(BaseModel):
    """Request body for batch document deletion.

    Attributes:
        doc_ids: Non-empty list of document UUIDs to permanently delete.
    """

    doc_ids: list[str]


class BatchDeleteResponse(BaseModel):
    """Response body for batch document deletion.

    Attributes:
        deleted: Number of documents that were actually deleted.
    """

    deleted: int


@router.delete("", response_model=BatchDeleteResponse)
async def delete_documents_batch(
    slug: str,
    body: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchDeleteResponse:
    """
    Permanently delete a batch of documents. Owner-only operation.

    Deletes all documents whose IDs are in doc_ids and that belong to the
    given organisation. IDs that do not exist or belong to another org are
    silently ignored (idempotent). Cascades to amendments and all child data.

    Parameters:
        slug:         URL slug of the owning organisation.
        body:         BatchDeleteRequest with the list of document IDs to delete.
        current_user: Injected via the get_current_user dependency.
        db:           Injected async DB session.

    Returns:
        BatchDeleteResponse with the count of documents deleted.

    Raises:
        HTTPException 403: If the caller is not the organisation owner.
        HTTPException 404: If the org is not found or the user is not a member.
        HTTPException 422: If doc_ids is empty.
    """
    if not body.doc_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="doc_ids must not be empty.",
        )
    try:
        count = await delete_documents(
            db=db, current_user=current_user, slug=slug, doc_ids=body.doc_ids
        )
    except ValueError as exc:
        msg = str(exc)
        if "Only the organisation owner" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
    return BatchDeleteResponse(deleted=count)


# ---------------------------------------------------------------------------
# Contributor public link
# ---------------------------------------------------------------------------


@router.post("/{doc_id}/contributor-token", response_model=ContributorTokenResponse)
async def generate_contributor_token(
    slug: str,
    doc_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContributorTokenResponse:
    """
    Generate (or regenerate) a contributor public link token for a document.

    Requires owner or admin role. If a token already exists it is replaced
    (the old link is immediately revoked).

    Parameters:
        slug:         URL slug of the owning organisation.
        doc_id:       UUID of the document.
        request:      FastAPI request (used to build the full contribution URL).
        current_user: Injected via the get_current_user dependency.
        db:           Injected async DB session.

    Returns:
        ContributorTokenResponse with the new token, creation timestamp, and URL.

    Raises:
        HTTPException 403: If the caller is not owner or admin, or if the org
            plan is Solo (contributor links require Team or Organisation).
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        org, membership = await _require_membership(db, current_user, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage contribution links.",
        )

    if org.plan not in (OrgPlan.team, OrgPlan.organisation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contributor links require a Team or Organisation plan.",
        )

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    token = secrets.token_hex(32)  # 64 hex chars
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.contributor_link_expire_days)
    doc.contributor_token = token
    doc.contributor_token_created_at = now
    doc.contributor_token_expires_at = expires_at
    await db.flush()

    base_url = str(request.base_url).rstrip("/")
    return ContributorTokenResponse(
        token=token,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        url=f"{base_url}/contribute/{token}",
        status="active",
    )


@router.delete("/{doc_id}/contributor-token", response_model=ContributorTokenResponse)
async def revoke_contributor_token(
    slug: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContributorTokenResponse:
    """
    Revoke the contributor public link for a document.

    Sets contributor_token to NULL, immediately invalidating the shareable link.
    Requires owner or admin role.

    Parameters:
        slug:         URL slug of the owning organisation.
        doc_id:       UUID of the document.
        current_user: Injected via the get_current_user dependency.
        db:           Injected async DB session.

    Returns:
        ContributorTokenResponse with all fields set to None (link revoked).

    Raises:
        HTTPException 403: If the caller is not owner or admin.
        HTTPException 404: If the org/doc is not found or the user is not a member.
    """
    try:
        org, membership = await _require_membership(db, current_user, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage contribution links.",
        )

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.org_id == org.id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    doc.contributor_token = None
    doc.contributor_token_created_at = None
    doc.contributor_token_expires_at = None
    await db.flush()

    return ContributorTokenResponse(
        token=None,
        created_at=None,
        expires_at=None,
        url=None,
        status=CONTRIBUTOR_LINK_STATUS_REVOKED,
    )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

_SAFE_FILENAME_RE = re.compile(r"[^\w\-]")


async def _fetch_amendments_for_export(
    db: AsyncSession, doc_id: str, include: str
) -> list[dict]:
    """
    Fetch amendments for the export appendix.

    Parameters:
        db:      Async SQLAlchemy session.
        doc_id:  UUID string of the document.
        include: 'accepted' to return only accepted amendments, 'all' to return all.

    Returns:
        Ordered list of amendment dicts ready for the export utilities, each with
        keys: number, author, section, original_text, proposed_text, justification,
        status, created_at.
    """
    query = (
        select(Amendment, User)
        .outerjoin(User, User.id == Amendment.author_id)
        .where(Amendment.doc_id == doc_id)
    )
    if include == "accepted":
        query = query.where(Amendment.status == AmendmentStatus.accepted)
    query = query.order_by(Amendment.created_at.asc())

    result = await db.execute(query)
    rows = result.all()

    amendments = []
    for index, (amend, user) in enumerate(rows, start=1):
        author = (
            (user.name or user.email)
            if user
            else (amend.contributor_name or amend.contributor_email or "Unknown")
        )
        amendments.append(
            {
                "number": index,
                "author": author,
                "section": amend.section,
                "original_text": amend.original_text,
                "proposed_text": amend.proposed_text,
                "justification": amend.justification,
                "status": amend.status.value,
                "created_at": amend.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return amendments


def _allowed_export_formats_for_plan(plan: OrgPlan) -> tuple[str, ...]:
    """
    Return the export formats available for a given organisation billing plan.

    Parameters:
        plan: Organisation billing plan.

    Returns:
        Tuple of format identifiers accepted by the export endpoints.
    """
    if plan == OrgPlan.organisation:
        return ("docx", "pdf", "txt", "csv", "json")
    if plan == OrgPlan.team:
        return ("docx", "pdf")
    return ("pdf",)

_EXPORT_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "txt":  "text/plain; charset=utf-8",
    "csv":  "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
}

_EXPORT_EXTENSIONS = {
    "docx": "docx",
    "pdf": "pdf",
    "txt": "txt",
    "csv": "csv",
    "json": "json",
}


@router.get("/{doc_id}/export")
async def export_document(
    slug: str,
    doc_id: str,
    format: str = Query(default="docx", pattern="^(docx|pdf|txt|csv|json)$"),
    include_amendments: str = Query(default="none", pattern="^(accepted|all|none)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export the consolidated document (original body + accepted amendments applied)
    as a downloadable file.  Requires owner or admin role.

    The consolidated text is generated by reusing the same logic as
    GET …/consolidated — accepted amendments are applied oldest-first.

    An optional amendments appendix can be appended using the include_amendments
    query parameter.

    Parameters:
        slug:               URL slug of the owning organisation.
        doc_id:             UUID of the document to export.
        format:             Output format — one of 'docx', 'pdf', 'txt', 'csv',
                            or 'json' (default: 'docx').
        include_amendments: Whether to append an amendments section — 'accepted', 'all',
                            or 'none' (default: 'none' for backwards compatibility).
        current_user:       Injected via the get_current_user dependency.
        db:                 Injected async DB session.

    Returns:
        Streaming file response with the correct Content-Type and
        Content-Disposition: attachment header.

    Raises:
        HTTPException 403: If the caller is a member (not owner/admin).
        HTTPException 404: If the org/doc is not found or the user is not a member.
        HTTPException 422: If the format or include_amendments query parameter is invalid.
    """
    # Resolve membership and enforce write-access (owner/admin only)
    try:
        org, membership = await _require_membership(db, current_user, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can export documents.",
        )

    fmt = format.lower()
    if fmt not in _allowed_export_formats_for_plan(org.plan):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{fmt.upper()} export is not available on the {org.plan.value.capitalize()} "
                "plan. Upgrade your plan to unlock this format."
            ),
        )

    # Get consolidated content (reuses existing service logic)
    try:
        consolidated = await get_consolidated(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    title = consolidated.title
    body = consolidated.body_with_amendments_applied

    # Build optional amendments appendix
    amendments_for_export: list[dict] | None = None
    if include_amendments != "none":
        amendments_for_export = await _fetch_amendments_for_export(
            db, doc_id, include_amendments
        )

    # Generate the file bytes
    if fmt == "docx":
        file_bytes = export_docx(title, body, amendments_for_export)
    elif fmt == "pdf":
        file_bytes = export_pdf(title, body, amendments_for_export)
    elif fmt == "txt":
        file_bytes = export_txt(title, body, amendments_for_export)
    elif fmt == "csv":
        file_bytes = export_csv(title, body, amendments_for_export)
    else:
        file_bytes = export_json(title, body, amendments_for_export)

    # Build a safe filename from the document title
    safe_stem = _SAFE_FILENAME_RE.sub("_", title)[:80].strip("_") or "document"
    filename = f"{safe_stem}.{_EXPORT_EXTENSIONS[fmt]}"

    return Response(
        content=file_bytes,
        media_type=_EXPORT_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{doc_id}/export/zip")
async def export_document_zip(
    slug: str,
    doc_id: str,
    include_amendments: str = Query(default="none", pattern="^(accepted|all|none)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export the consolidated document as a ZIP archive containing every format
    available on the current plan in a single download. Requires owner or admin role.

    The same consolidated body used by GET …/export is reused here so results
    are identical to downloading each format individually.  An optional amendments
    appendix can be included using the include_amendments query parameter.

    Parameters:
        slug:               URL slug of the owning organisation.
        doc_id:             UUID of the document to export.
        include_amendments: Whether to append an amendments section — 'accepted', 'all',
                            or 'none' (default: 'none' for backwards compatibility).
        current_user: Injected via the get_current_user dependency.
        db:      Injected async DB session.

    Returns:
        Streaming ZIP response with Content-Disposition: attachment header.
        The archive contains every export format unlocked by the current plan.

    Raises:
        HTTPException 403: If the caller is a member (not owner/admin).
        HTTPException 404: If the org/doc is not found or the user is not a member.
        HTTPException 422: If the include_amendments query parameter is invalid.
    """
    # Resolve membership and enforce write-access (owner/admin only)
    try:
        org, membership = await _require_membership(db, current_user, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if membership.role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can export documents.",
        )

    # Get consolidated content (reuses existing service logic)
    try:
        consolidated = await get_consolidated(
            db=db, current_user=current_user, slug=slug, doc_id=doc_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    title = consolidated.title
    body = consolidated.body_with_amendments_applied

    # Build optional amendments appendix (same logic as single-format export)
    amendments_for_export: list[dict] | None = None
    if include_amendments != "none":
        amendments_for_export = await _fetch_amendments_for_export(
            db, doc_id, include_amendments
        )

    # Build a safe filename stem from the document title
    safe_stem = _SAFE_FILENAME_RE.sub("_", title)[:80].strip("_") or "document"

    # Generate every format available on the current plan.
    formats = {}
    for fmt in _allowed_export_formats_for_plan(org.plan):
        filename = f"{safe_stem}.{_EXPORT_EXTENSIONS[fmt]}"
        if fmt == "docx":
            formats[filename] = export_docx(title, body, amendments_for_export)
        elif fmt == "pdf":
            formats[filename] = export_pdf(title, body, amendments_for_export)
        elif fmt == "txt":
            formats[filename] = export_txt(title, body, amendments_for_export)
        elif fmt == "csv":
            formats[filename] = export_csv(title, body, amendments_for_export)
        else:
            formats[filename] = export_json(title, body, amendments_for_export)

    # Bundle into an in-memory ZIP archive
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, file_bytes in formats.items():
            zf.writestr(filename, file_bytes)

    zip_filename = f"{safe_stem}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
