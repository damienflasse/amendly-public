"""
Request/response schemas for inbound contact and support messages.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, EmailStr, field_validator


def _clean_non_empty(value: str, *, field_name: str, max_length: int) -> str:
    """Trim a required string field and enforce a maximum length."""
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer")
    return value


class ContactRequest(BaseModel):
    """Body for POST /api/contact."""

    first_name: str
    last_name: str
    email: EmailStr
    message: str
    website: str | None = None

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        return _clean_non_empty(value, field_name="first_name", max_length=120)

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        return _clean_non_empty(value, field_name="last_name", max_length=120)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _clean_non_empty(value, field_name="message", max_length=5000)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if len(value) > 255:
            raise ValueError("website must be 255 characters or fewer")
        return value or None


class SupportCategory(str, enum.Enum):
    """Allowed support request categories."""

    billing = "billing"
    account = "account"
    documents = "documents"
    export = "export"
    other = "other"


class SupportRequest(BaseModel):
    """Body for POST /api/support."""

    category: SupportCategory
    subject: str
    message: str

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        return _clean_non_empty(value, field_name="subject", max_length=200)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _clean_non_empty(value, field_name="message", max_length=5000)


class InboxAcceptedResponse(BaseModel):
    """Minimal success response for inbound message endpoints."""

    ok: bool = True
