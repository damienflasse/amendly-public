"""
Pydantic request/response schemas for the billing API.

These are the data-transfer objects used by the /api/billing routes.
"""

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    """Body for POST /api/billing/checkout."""

    slug: str
    success_url: str
    cancel_url: str
    plan_name: str = "solo"  # Which plan tier: 'solo', 'team', 'organisation'
    annual: bool = False  # True → use stripe_price_id_annual; False → monthly


class CheckoutResponse(BaseModel):
    """Response for POST /api/billing/checkout."""

    checkout_url: str


class PortalRequest(BaseModel):
    """Body for POST /api/billing/portal."""

    slug: str


class PortalResponse(BaseModel):
    """Response for POST /api/billing/portal."""

    portal_url: str
