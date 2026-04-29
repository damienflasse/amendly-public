"""
Pydantic schemas for prospect admin endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class ProspectCreate(BaseModel):
    """Request body for POST /api/admin/prospects."""

    email: EmailStr
    name: str | None = None
    org_name: str | None = None
    notes: str | None = None


class ProspectUpdate(BaseModel):
    """Request body for PATCH /api/admin/prospects/{id} — all fields optional."""

    email: EmailStr | None = None
    name: str | None = None
    org_name: str | None = None
    notes: str | None = None
    status: str | None = None  # Validated against ProspectStatus in the service


class ProspectEmailRequest(BaseModel):
    """
    Request body for POST /api/admin/prospects/{id}/email.

    Either supply template_key to use an existing email template,
    or supply subject + html_body for a free-form email.
    At least one of (template_key, subject+html_body) must be provided.
    """

    template_key: str | None = None
    subject: str | None = None
    html_body: str | None = None


class ProspectResponse(BaseModel):
    """Response payload for a single prospect."""

    id: str
    email: str
    name: str | None
    org_name: str | None
    notes: str | None
    status: str
    created_at: str  # ISO-8601
    updated_at: str  # ISO-8601
