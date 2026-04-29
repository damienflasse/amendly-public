"""
Inbound message API routes for the public contact page and authenticated support.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.inbox import ContactRequest, InboxAcceptedResponse, SupportRequest
from app.services.inbox import send_contact_message, send_support_message
from app.utils.rate_limit import check_redis_rate_limit, get_client_ip, get_redis_client

router = APIRouter(tags=["inbox"])
logger = logging.getLogger(__name__)

_contact_rate_limit_window: dict[str, list[float]] = defaultdict(list)
_contact_rate_limit_redis_client = None
_CONTACT_REDIS_KEY_PREFIX = "rl:contact:ip:"
_CONTACT_RATE_LIMIT = 5
_CONTACT_WINDOW_SECONDS = 3600


def _get_contact_rate_limit_redis():
    """Return the Redis client used for public contact rate limiting."""
    global _contact_rate_limit_redis_client
    if _contact_rate_limit_redis_client is not None:
        return _contact_rate_limit_redis_client
    _contact_rate_limit_redis_client = get_redis_client(
        "contact_rate_limit",
        logger=logger,
        unavailable_message=(
            "Redis unavailable for public contact rate limiting; "
            "using in-memory fallback."
        ),
    )
    return _contact_rate_limit_redis_client


async def _check_contact_rate_limit(ip: str) -> None:
    """Raise HTTP 429 when the public contact form limit is exceeded."""
    allowed = await check_redis_rate_limit(
        _get_contact_rate_limit_redis(),
        f"{_CONTACT_REDIS_KEY_PREFIX}{ip}",
        max_count=_CONTACT_RATE_LIMIT,
        ttl_seconds=_CONTACT_WINDOW_SECONDS,
        logger=logger,
        failure_message=(
            "Redis rate-limit check failed for public contact; "
            "using in-memory fallback."
        ),
    )
    if allowed is True:
        return
    if allowed is False:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many contact requests. Please try again later.",
            headers={"Retry-After": str(_CONTACT_WINDOW_SECONDS)},
        )

    now = time.monotonic()
    cutoff = now - _CONTACT_WINDOW_SECONDS
    _contact_rate_limit_window[ip] = [t for t in _contact_rate_limit_window[ip] if t > cutoff]
    if len(_contact_rate_limit_window[ip]) >= _CONTACT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many contact requests. Please try again later.",
            headers={"Retry-After": str(_CONTACT_WINDOW_SECONDS)},
        )
    _contact_rate_limit_window[ip].append(now)


@router.post("/api/contact", response_model=InboxAcceptedResponse)
async def post_contact(
    body: ContactRequest,
    request: Request,
) -> InboxAcceptedResponse:
    """
    Receive a public contact message and forward it to the Amendly inbox.
    """
    ip = get_client_ip(request)
    await _check_contact_rate_limit(ip)

    if body.website:
        return InboxAcceptedResponse(ok=True)

    try:
        await send_contact_message(body)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Contact message delivery failed. Please try again later.",
        ) from exc

    return InboxAcceptedResponse(ok=True)


@router.post("/api/support", response_model=InboxAcceptedResponse)
async def post_support(
    body: SupportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InboxAcceptedResponse:
    """
    Receive an authenticated support request and forward it to the Amendly inbox.
    """
    try:
        await send_support_message(db, current_user=current_user, payload=body)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Support request delivery failed. Please try again later.",
        ) from exc

    return InboxAcceptedResponse(ok=True)
