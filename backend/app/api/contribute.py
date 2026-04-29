"""
Public contribution API — no authentication required.

Endpoints:
  GET  /api/contribute/{token}  — fetch document metadata by contributor token.
  POST /api/contribute/{token}  — submit an anonymous amendment to the document.

These endpoints are intentionally unauthenticated so that external contributors
(federation members, NGO delegates, etc.) can submit amendments via a shareable
link without creating an Amendly account.

Rate limiting on POST:
  A Redis-backed counter tracks submission counts per IP address with a 1-hour
  window when Redis is reachable. An in-memory rolling window remains as a
  fallback in local development and test environments. Limit: 10 submissions
  per IP per hour.
"""

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.amendment import Amendment, AmendmentStatus, AmendmentType
from app.models.document import Document, DocumentStatus
from app.models.organisation import Organisation, OrgPlan
from app.schemas.amendment import AmendmentResponse, ContributorAmendmentCreate
from app.services.amendment import _format_amendment
from app.services.document import (
    CONTRIBUTOR_LINK_STATUS_EXPIRED,
    _coerce_utc,
    get_contributor_link_status,
)
from app.services.plan_config import get_external_contributor_limit_for_plan
from app.utils.rate_limit import check_redis_rate_limit, get_client_ip, get_redis_client
from app.utils.turnstile import verify_turnstile

router = APIRouter(prefix="/api/contribute", tags=["contribute"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

# In-memory fallback structure: { ip_address: [(timestamp, …), …] }
_rate_limit_window: dict[str, list[float]] = defaultdict(list)
_rate_limit_redis_client = None
_REDIS_RATE_LIMIT_KEY_PREFIX = "rl:contribute:ip:"
_RATE_LIMIT = 10
_WINDOW_SECONDS = 3600


def _normalise_contributor_identity(name: str, email: str | None) -> str:
    """
    Build a stable identity key for an anonymous contributor submission.

    Email is preferred because it is more stable across repeated submissions.
    When no email is provided, the trimmed lower-cased contributor name is used.

    Parameters:
        name: Contributor display name.
        email: Optional contributor email.

    Returns:
        Lower-cased identity key.
    """
    if email and email.strip():
        return email.strip().lower()
    return name.strip().lower()


def _get_rate_limit_redis():
    """
    Return a shared Redis client for the public contribution rate limiter.

    The client is created lazily from REDIS_URL. If Redis cannot be initialised,
    callers should fall back to the in-memory limiter so local development and
    test runs still work without external services.
    """
    global _rate_limit_redis_client
    if _rate_limit_redis_client is not None:
        return _rate_limit_redis_client
    _rate_limit_redis_client = get_redis_client(
        "contribute_rate_limit",
        logger=logger,
        unavailable_message=(
            "Redis unavailable for public contribution rate limiting; "
            "using in-memory fallback."
        ),
    )
    return _rate_limit_redis_client


async def _check_rate_limit(ip: str) -> None:
    """
    Raise HTTP 429 if the given IP has exceeded the submission rate limit.

    Redis is used when available so the limit is shared across workers and
    processes. If Redis is unavailable, an in-memory rolling window is used as
    a local fallback.

    Parameters:
        ip: The client's IP address string.

    Raises:
        HTTPException 429: If the rate limit has been exceeded.
    """
    allowed = await check_redis_rate_limit(
        _get_rate_limit_redis(),
        f"{_REDIS_RATE_LIMIT_KEY_PREFIX}{ip}",
        max_count=_RATE_LIMIT,
        ttl_seconds=_WINDOW_SECONDS,
        logger=logger,
        failure_message=(
            "Redis rate-limit check failed for public contribution; "
            "using in-memory fallback."
        ),
    )
    if allowed is True:
        return
    if allowed is False:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please try again later.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )

    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    _rate_limit_window[ip] = [t for t in _rate_limit_window[ip] if t > cutoff]
    if len(_rate_limit_window[ip]) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please try again later.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
    _rate_limit_window[ip].append(now)


# ---------------------------------------------------------------------------
# Public document preview schema (minimal — no full body for performance)
# ---------------------------------------------------------------------------

class PublicDocumentResponse(BaseModel):
    """Minimal document metadata returned by GET /api/contribute/{token}.

    Does not require authentication. Returns only fields needed to render the
    contribution form: title, body, status, and the owning organisation's name.

    Attributes:
        doc_id:    Document UUID — used to construct amendment API calls.
        title:     Document title.
        body:      Full document body (HTML or plain text).
        status:    Document lifecycle status ('open' is the only valid state).
        org_name:  Display name of the owning organisation.
    """

    doc_id: str
    title: str
    body: str | None
    status: str
    org_name: str
    contributor_link_status: str
    contributor_token_expires_at: str | None = None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/{token}", response_model=PublicDocumentResponse)
async def get_public_document(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicDocumentResponse:
    """
    Look up a document by its contributor token and return public metadata.

    No authentication is required. Returns 404 if the token is invalid or the
    document is not open (draft and closed documents reject the link).

    Parameters:
        token: 64-char hex contributor token from the URL.
        db:    Injected async DB session.

    Returns:
        PublicDocumentResponse with title, body, status, and org name.

    Raises:
        HTTPException 404: Token unknown, document closed/draft, or token NULL.
    """
    result = await db.execute(
        select(Document, Organisation)
        .join(Organisation, Organisation.id == Document.org_id)
        .where(Document.contributor_token == token)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution link not found or has been revoked.",
        )

    doc, org = row
    if doc.status != DocumentStatus.open:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This document is no longer accepting contributions.",
        )
    link_status = get_contributor_link_status(doc, now=datetime.now(UTC))
    if link_status == CONTRIBUTOR_LINK_STATUS_EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This contribution link has expired. Please ask the organisation to generate a new link.",
        )

    return PublicDocumentResponse(
        doc_id=doc.id,
        title=doc.title,
        body=doc.body,
        status=doc.status.value,
        org_name=org.name,
        contributor_link_status=link_status,
        contributor_token_expires_at=(
            _coerce_utc(doc.contributor_token_expires_at).isoformat()
            if doc.contributor_token_expires_at
            else None
        ),
    )


@router.post("/{token}", response_model=AmendmentResponse, status_code=status.HTTP_201_CREATED)
async def submit_public_amendment(
    token: str,
    body: ContributorAmendmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AmendmentResponse:
    """
    Submit an anonymous amendment to a document identified by its contributor token.

    No authentication is required. The submitter provides their name (required)
    and email (optional) as part of the request body.

    Rate limited: 10 submissions per IP per hour.

    Parameters:
        token:   64-char hex contributor token from the URL.
        body:    ContributorAmendmentCreate request body.
        request: FastAPI Request (used for rate-limit IP extraction).
        db:      Injected async DB session.

    Returns:
        AmendmentResponse for the newly created amendment (201 Created).

    Raises:
        HTTPException 404: Token unknown or document not open.
        HTTPException 429: Rate limit exceeded or the plan's external-contributor cap is reached.
        HTTPException 403: Anti-bot check failed.
        HTTPException 422: Validation error (missing required fields).
    """
    ip = get_client_ip(request, trust_x_forwarded_for=True)
    await _check_rate_limit(ip)
    if not await verify_turnstile(
        body.cf_turnstile_token,
        ip,
        fail_open=False,
        context="public_contribution",
        expected_action="public_contribution",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anti-bot verification failed. Please try again.",
        )

    result = await db.execute(
        select(Document, Organisation)
        .join(Organisation, Organisation.id == Document.org_id)
        .where(Document.contributor_token == token)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution link not found or has been revoked.",
        )
    doc, org = row
    if doc.status != DocumentStatus.open:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This document is no longer accepting contributions.",
        )
    if get_contributor_link_status(doc, now=datetime.now(UTC)) == CONTRIBUTOR_LINK_STATUS_EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This contribution link has expired. Please ask the organisation to generate a new link.",
        )

    # Plan gate: Solo cannot accept public-link contributions. Team and
    # Organisation use plan_config-driven contributor caps.
    if org.plan == OrgPlan.solo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External contributions require a Team or Organisation plan.",
        )

    contributor_limit = await get_external_contributor_limit_for_plan(db, org.plan.value)
    if contributor_limit is not None:
        # Lock the document row for the duration of this transaction so that
        # concurrent submissions cannot both pass the cap check simultaneously
        # (classic TOCTOU race condition). SQLite used in tests ignores FOR UPDATE.
        await db.execute(
            select(Document.id).where(Document.id == doc.id).with_for_update()
        )

        identity = _normalise_contributor_identity(
            body.contributor_name,
            body.contributor_email,
        )
        identity_expr = func.lower(
            func.coalesce(
                func.nullif(Amendment.contributor_email, ""),
                Amendment.contributor_name,
            )
        )
        existing_result = await db.execute(
            select(func.count()).where(
                Amendment.doc_id == doc.id,
                Amendment.author_id.is_(None),
                identity_expr == identity,
            )
        )
        existing_count = existing_result.scalar_one()
        if existing_count == 0:
            count_result = await db.execute(
                select(func.count(func.distinct(identity_expr))).where(
                    Amendment.doc_id == doc.id,
                    Amendment.author_id.is_(None),
                )
            )
            contributor_count = count_result.scalar_one()
            if contributor_count >= contributor_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "This document has reached the external contributor limit "
                        f"({contributor_limit}) for the {org.plan.value.capitalize()} plan. "
                        "Update billing to increase the quota."
                    ),
                )

    amendment = Amendment(
        id=str(_uuid.uuid4()),
        doc_id=doc.id,
        amendment_type=AmendmentType(body.amendment_type),
        section=body.section,
        original_text=body.original_text,
        proposed_text=body.proposed_text,
        justification=body.justification,
        status=AmendmentStatus.pending,
        author_id=None,  # anonymous — no registered user
        contributor_name=body.contributor_name,
        contributor_email=body.contributor_email,
    )
    db.add(amendment)
    await db.flush()

    return _format_amendment(
        amendment,
        author_name=body.contributor_name,
        author_email=body.contributor_email,
    )
