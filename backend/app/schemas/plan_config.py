"""
Pydantic schemas for the plan configuration API.

Used by:
  - GET  /api/plans            (public — PlanConfigResponse list)
  - GET  /api/admin/plans      (superuser — PlanConfigResponse list)
  - PATCH /api/admin/plans/{name} (superuser — PlanConfigUpdate body, PlanConfigResponse)
"""

from typing import Optional

from pydantic import BaseModel


class PlanConfigResponse(BaseModel):
    """Read-only representation of a plan configuration row."""

    plan_name: str
    base_price_cents: int
    included_users: int
    extra_user_price_cents: int
    max_active_documents: Optional[int]  # None = unlimited
    max_external_contributors: Optional[int]  # None = unlimited
    stripe_price_id: str
    stripe_price_id_annual: str
    features: list[str]
    is_active: bool
    updated_at: str  # ISO-8601 string

    model_config = {"from_attributes": True}


class PlanConfigUpdate(BaseModel):
    """
    Partial update payload for PATCH /api/admin/plans/{name}.

    All fields are optional.  A value of -1 for max_active_documents is a
    sentinel that means 'set to NULL' (unlimited).  Passing None leaves the
    field unchanged.
    """

    base_price_cents: Optional[int] = None
    included_users: Optional[int] = None
    extra_user_price_cents: Optional[int] = None
    max_active_documents: Optional[int] = None  # -1 = sentinel → NULL (unlimited)
    max_external_contributors: Optional[int] = None  # -1 = sentinel → NULL (unlimited)
    stripe_price_id: Optional[str] = None
    stripe_price_id_annual: Optional[str] = None
    features: Optional[list[str]] = None
    is_active: Optional[bool] = None
