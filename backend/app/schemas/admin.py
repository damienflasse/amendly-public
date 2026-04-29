"""
Pydantic schemas for the superadmin dashboard API.

Used by:
  - GET  /api/admin/stats                     — platform overview (AdminStatsResponse)
  - GET  /api/admin/organisations             — all orgs (list[AdminOrgResponse])
  - PATCH /api/admin/organisations/{id}/plan  — change an org's plan (AdminOrgPlanUpdate body)
  - GET  /api/admin/users                     — all users with filters (list[AdminUserResponse])
  - PATCH /api/admin/users/{id}               — update user plan / expiry (AdminUserUpdate body)
"""

from typing import Optional

from pydantic import BaseModel


class OrgRegistrationPoint(BaseModel):
    """A single data point for the org-registration sparkline."""

    date: str   # ISO-8601 date (YYYY-MM-DD)
    count: int


class AdminStatsResponse(BaseModel):
    """Platform-level aggregated statistics for the superadmin dashboard."""

    total_orgs: int
    total_users: int
    orgs_by_plan: dict[str, int]                   # { 'solo': N, 'team': N, 'organisation': N }
    estimated_mrr_cents: int                        # sum of (org_count × plan.base_price_cents)
    total_amendments: int                           # all amendments across the platform
    total_open_documents: int                       # documents with status = open
    orgs_last_30_days: list[OrgRegistrationPoint]  # daily registration counts (30 days)


class AdminOrgResponse(BaseModel):
    """Organisation row enriched with computed metrics for the admin table."""

    id: str
    name: str
    slug: str
    plan: str
    member_count: int
    document_count: int
    amendment_count: int              # total amendments submitted across all org documents
    last_activity_at: Optional[str]   # ISO-8601 — latest amendment or document created_at
    stripe_customer_id: Optional[str]
    created_at: str   # ISO-8601

    model_config = {"from_attributes": True}


class AdminOrgPlanUpdate(BaseModel):
    """Body for PATCH /api/admin/organisations/{id}/plan."""

    plan: str   # 'solo' | 'team' | 'organisation'


class AdminUserResponse(BaseModel):
    """User row enriched with org memberships for the admin users table."""

    id: str
    email: str
    name: Optional[str]
    company: Optional[str]
    plan: str
    plan_expires_at: Optional[str]   # ISO-8601 or None
    created_at: str                  # ISO-8601
    is_deleted: bool
    is_superuser: bool
    org_count: int
    org_names: list[str]

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    """Body for PATCH /api/admin/users/{id}."""

    plan: Optional[str] = None            # 'solo' | 'team' | 'organisation'
    plan_expires_at: Optional[str] = None  # ISO-8601 datetime or null string to clear
