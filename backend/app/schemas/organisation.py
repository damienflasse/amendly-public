"""
Pydantic request/response schemas for the organisations API.

These are the data-transfer objects used by the /api/organisations routes.
They are separate from the SQLAlchemy ORM models in app/models/.
"""

import re

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class OrganisationCreate(BaseModel):
    """Body for POST /api/organisations — create a new organisation."""

    name: str
    slug: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Ensure name is non-empty after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return v

    @field_validator("slug")
    @classmethod
    def slug_is_valid(cls, v: str) -> str:
        """
        Validate that slug is lowercase, alphanumeric with hyphens, 3–100 chars.

        Rules:
          - Lowercase letters, digits, and hyphens only (no spaces or special characters).
          - Must start and end with a letter or digit (no leading/trailing hyphen).
          - Length between 3 and 100 characters.

        Raises:
            ValueError: With a human-readable message if the slug fails validation.
        """
        v = v.strip().lower()
        if len(v) < 3 or len(v) > 100:
            raise ValueError(
                "URL slug must be between 3 and 100 characters long."
            )
        if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*[a-z0-9]", v):
            raise ValueError(
                "URL slug must contain only lowercase letters, digits, and hyphens, "
                "and must start and end with a letter or digit (e.g. 'acme-federation')."
            )
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class OrganisationResponse(BaseModel):
    """Organisation fields returned by the API."""

    id: str
    name: str
    slug: str
    plan: str
    created_at: str  # ISO-8601 string — serialised in the service layer

    model_config = {"from_attributes": True}


class MembershipResponse(BaseModel):
    """
    Organisation + role pair returned by GET /api/organisations/me.

    Returns the organisation details alongside the calling user's role.
    """

    id: str
    name: str
    slug: str
    plan: str
    created_at: str
    role: str  # owner | admin | member

    model_config = {"from_attributes": True}


class MemberDetail(BaseModel):
    """
    Single member record returned by GET /api/organisations/{slug}/members.

    Contains user identity, role, when the membership was created, and the
    timestamp of the member's most recent activity log entry in this org.
    """

    user_id: str
    email: str
    name: str | None
    role: str                       # owner | admin | member
    joined_at: str                  # ISO-8601 string
    last_activity_at: str | None    # ISO-8601 string or null if no activity recorded

    model_config = {"from_attributes": True}


class OrganisationUpdate(BaseModel):
    """Body for PATCH /api/organisations/{slug} — update name and/or slug."""

    name: str | None = None
    slug: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        """Ensure name, if provided, is non-empty and within length limit."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 255:
            raise ValueError("name must be 255 characters or fewer")
        return v

    @field_validator("slug")
    @classmethod
    def slug_is_valid(cls, v: str | None) -> str | None:
        """
        Validate that slug, if provided, is lowercase alphanumeric with hyphens, 3–60 chars.

        Rules:
          - Lowercase letters, digits, and hyphens only.
          - Must start and end with a letter or digit.
          - Length between 3 and 60 characters.

        Raises:
            ValueError: With a human-readable message if the slug fails validation.
        """
        if v is None:
            return v
        v = v.strip().lower()
        if len(v) < 3 or len(v) > 60:
            raise ValueError("URL slug must be between 3 and 60 characters long.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*[a-z0-9]", v):
            raise ValueError(
                "URL slug must contain only lowercase letters, digits, and hyphens, "
                "and must start and end with a letter or digit."
            )
        return v


class RoleChangeRequest(BaseModel):
    """Body for PUT /api/organisations/{slug}/members/{user_id}/role."""

    role: str  # admin | member (owner cannot be set via API)


class OrgStatsResponse(BaseModel):
    """Activity counters returned by GET /api/organisations/{slug}/stats."""

    active_docs: int        # documents with status = open
    pending_amendments: int # pending amendments across all org documents
    member_count: int       # total organisation members
