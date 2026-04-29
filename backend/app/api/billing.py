"""
Billing API routes.

Endpoints:
  POST /api/billing/checkout          — create a Stripe Checkout session (owner only)
  POST /api/billing/portal            — create a Stripe Customer Portal session (owner only)
  POST /api/billing/webhook           — Stripe webhook receiver (unauthenticated,
                                        validated by Stripe-Signature header)

The checkout and portal endpoints require a valid Bearer JWT (org owner only).
The webhook endpoint is called by Stripe; it validates the request using the
Stripe-Signature header and the STRIPE_WEBHOOK_SECRET env var — no JWT is used.
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.billing import CheckoutRequest, CheckoutResponse, PortalRequest, PortalResponse
from app.services.billing import create_checkout_session, create_portal_session, handle_stripe_event

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
)
async def post_checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout session for a paid organisation plan.

    Only the organisation owner may call this endpoint.
    Returns a one-time Stripe Checkout URL to which the frontend redirects the user.

    Parameters:
        body: CheckoutRequest containing the org slug and redirect URLs.
        current_user: Injected via get_current_user (must be org owner).
        db: Injected async DB session.

    Returns:
        CheckoutResponse with { checkout_url }.

    Raises:
        HTTPException 400: If Stripe is not configured.
        HTTPException 403: If the caller is not the org owner.
        HTTPException 404: If the org does not exist or the caller is not a member.
    """
    try:
        url = await create_checkout_session(
            db=db,
            current_user=current_user,
            slug=body.slug,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            plan_name=body.plan_name,
            annual=body.annual,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not configured" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        if "owner" in msg.lower():
            # 403 only ever reaches authenticated members — slug disclosure is acceptable here
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        # 404 is returned both when the org doesn't exist and when the caller
        # is not a member (service uses a JOIN so both cases produce the same
        # code path). Use a generic message to avoid echoing private slugs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from exc

    return CheckoutResponse(checkout_url=url)


@router.post(
    "/portal",
    response_model=PortalResponse,
    status_code=status.HTTP_200_OK,
)
async def post_portal(
    body: PortalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalResponse:
    """
    Create a Stripe Customer Portal session for an organisation.

    Only the organisation owner may call this endpoint. The portal lets
    the subscription holder manage billing details, update payment methods,
    and cancel the subscription.

    Parameters:
        body: PortalRequest containing the org slug.
        current_user: Injected via get_current_user (must be org owner).
        db: Injected async DB session.

    Returns:
        PortalResponse with { portal_url }.

    Raises:
        HTTPException 400: If Stripe is not configured or the org has no
                           Stripe Customer ID (upgrade first).
        HTTPException 403: If the caller is not the org owner.
        HTTPException 404: If the org does not exist or the caller is not a member.
    """
    return_url = settings.stripe_portal_return_url or (
        f"https://{settings.domain}/orgs/{body.slug}/billing"
    )
    try:
        url = await create_portal_session(
            db=db,
            current_user=current_user,
            slug=body.slug,
            return_url=return_url,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not configured" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        if "subscription" in msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        if "owner" in msg.lower():
            # 403 only ever reaches authenticated members — slug disclosure is acceptable here
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg) from exc
        # Generic 404 — service uses a JOIN so org-not-found and not-a-member
        # are indistinguishable; avoid echoing private slugs.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.") from exc

    return PortalResponse(portal_url=url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive and process Stripe webhook events.

    Stripe calls this endpoint with a signed payload. The Stripe-Signature header
    is verified against STRIPE_WEBHOOK_SECRET before any business logic runs.

    Handled events:
      - checkout.session.completed    → set org.plan from Stripe metadata
      - customer.subscription.deleted → set org.plan = 'solo'

    All other event types return {"status": "ignored"}.

    Parameters:
        request: Raw FastAPI request (payload read as bytes for signature check).
        db: Injected async DB session.

    Returns:
        {"status": "ok"} on success, {"status": "ignored"} for unhandled events.

    Raises:
        HTTPException 400: If the signature is invalid or the payload is malformed.
        HTTPException 400: If STRIPE_WEBHOOK_SECRET is not configured.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe webhook secret is not configured.",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook payload error: {exc}",
        ) from exc

    await handle_stripe_event(db=db, event=event)
    return {"status": "ok"}
