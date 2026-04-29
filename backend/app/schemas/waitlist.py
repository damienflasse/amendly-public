"""
Pydantic schemas for the waitlist feature.

WaitlistCreate  — inbound payload from the public POST /api/v1/waitlist endpoint.
WaitlistResponse — outbound representation returned to the admin list endpoint.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class WaitlistCreate(BaseModel):
    """Payload for joining the waitlist."""

    email: EmailStr
    source: str | None = None
    turnstile_token: str | None = None


class WaitlistResponse(BaseModel):
    """Read model for a single waitlist entry (admin use)."""

    id: str
    email: str
    source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
