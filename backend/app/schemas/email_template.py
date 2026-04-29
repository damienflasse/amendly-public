"""
Pydantic schemas for email template admin endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel


class EmailTemplateResponse(BaseModel):
    """Response payload for a single email template."""

    template_key: str
    subject: str
    html_body: str
    variables: list[str]
    updated_at: str | None  # ISO-8601 or None if using the hardcoded default
    is_customised: bool     # True if a DB override exists; False = using default


class EmailTemplateUpdate(BaseModel):
    """Request body for PATCH /api/admin/email-templates/{key}."""

    subject: str
    html_body: str
