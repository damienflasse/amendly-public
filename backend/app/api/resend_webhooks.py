"""
Resend webhook receiver.

Receives signed email lifecycle events such as sent, delivered, bounced, and
complained so production delivery issues can be diagnosed from application logs.
"""

import json
import logging
from typing import Any

import resend
from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/webhooks/resend", tags=["webhooks"])


def _svix_headers(request: Request) -> dict[str, str]:
    """
    Extract the Svix signature headers used by Resend webhooks.

    Returns:
        Mapping with keys expected by `resend.Webhooks.verify`.
    """
    return {
        "id": request.headers.get("svix-id", ""),
        "timestamp": request.headers.get("svix-timestamp", ""),
        "signature": request.headers.get("svix-signature", ""),
    }


def _email_context(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Pull a compact email context summary from a Resend webhook payload.

    Returns:
        Dict containing the event type and the most useful delivery fields.
    """
    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}

    to_value = data.get("to")
    if isinstance(to_value, list):
        recipient = ",".join(str(item) for item in to_value)
    else:
        recipient = to_value

    return {
        "type": payload.get("type"),
        "created_at": payload.get("created_at"),
        "email_id": data.get("email_id") or data.get("id"),
        "recipient": recipient,
        "subject": data.get("subject"),
        "from": data.get("from"),
        "bounce_type": data.get("bounce", {}).get("type") if isinstance(data.get("bounce"), dict) else None,
        "bounce_subtype": data.get("bounce", {}).get("subType") if isinstance(data.get("bounce"), dict) else None,
    }


def _log_webhook_event(payload: dict[str, Any]) -> None:
    """
    Log a verified Resend webhook payload at an appropriate severity.

    Bounces, complaints, and delivery delays are warnings; delivered/sent events
    are info-level.
    """
    ctx = _email_context(payload)
    event_type = str(ctx["type"] or "unknown")
    log_method = logger.warning if event_type in {
        "email.bounced",
        "email.complained",
        "email.delivery_delayed",
        "email.failed",
    } else logger.info
    log_method(
        "Resend webhook event=%s email_id=%s recipient=%s subject=%s from=%s bounce_type=%s bounce_subtype=%s created_at=%s.",
        event_type,
        ctx["email_id"] or "unknown",
        ctx["recipient"] or "unknown",
        ctx["subject"] or "unknown",
        ctx["from"] or "unknown",
        ctx["bounce_type"] or "unknown",
        ctx["bounce_subtype"] or "unknown",
        ctx["created_at"] or "unknown",
    )


@router.post("", status_code=status.HTTP_200_OK)
async def resend_webhook(request: Request) -> dict[str, str]:
    """
    Receive and verify Resend webhook events.

    Raises:
        HTTPException 400: Missing signing secret, invalid signature, or invalid
        JSON payload.
    """
    if not settings.resend_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resend webhook secret is not configured.",
        )

    body = (await request.body()).decode("utf-8")
    headers = _svix_headers(request)

    try:
        resend.Webhooks.verify(
            {
                "payload": body,
                "headers": headers,
                "webhook_secret": settings.resend_webhook_secret,
            }
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Resend signature: {exc}",
        ) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Resend webhook JSON payload.",
        ) from exc

    _log_webhook_event(payload)
    return {"status": "ok"}
