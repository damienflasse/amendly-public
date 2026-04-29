"""
Pydantic request/response schemas for the invitation API.

These are the data-transfer objects used by the /api/organisations/{slug}/invite routes.
They are separate from the SQLAlchemy ORM models in app/models/.
"""

from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class InviteCreate(BaseModel):
    """Body for POST /api/organisations/{slug}/invite."""

    email: EmailStr
    turnstile_token: str | None = None

    @field_validator("turnstile_token")
    @classmethod
    def normalise_turnstile_token(cls, value: str | None) -> str | None:
        """Trim the Turnstile token and collapse blank values to None."""
        if value is None:
            return None
        value = value.strip()
        return value or None


class InviteAccept(BaseModel):
    """Body for POST /api/invitations/accept."""

    token: str
    turnstile_token: str | None = None

    @field_validator("turnstile_token")
    @classmethod
    def normalise_turnstile_token(cls, value: str | None) -> str | None:
        """Trim the Turnstile token and collapse blank values to None."""
        if value is None:
            return None
        value = value.strip()
        return value or None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class InvitationResponse(BaseModel):
    """Invitation fields returned by the API."""

    id: str
    org_id: str
    email: str
    created_at: str   # ISO-8601 string
    expires_at: str   # ISO-8601 string
    accepted_at: str | None

    model_config = {"from_attributes": True}


class InvitationPreview(BaseModel):
    """
    Public preview of an invitation — returned by GET /api/invitations/preview.

    Contains only the information needed to render the accept-invitation page
    before the user authenticates. No sensitive data is exposed.
    """

    org_name: str
    email: str
    expires_at: str   # ISO-8601 string
