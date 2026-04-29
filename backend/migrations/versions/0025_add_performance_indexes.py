"""Add performance indexes on amendments and memberships.

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-03 00:00:00.000000

Reason for change:
  Several hot-path queries were running without composite indexes:
    - amendments(doc_id, status): used by pending_count sub-queries on every
      document list response and by the consolidation/review endpoints.
    - amendments(status): used by admin dashboards and plan-gated counters.
    - memberships(org_id, role): used by _require_membership and admin-role
      lookups whenever an owner/admin check is performed.
  Adding these indexes eliminates sequential scans on large orgs and reduces
  query latency on the amendment workflow critical path.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite and single-column indexes for amendments and memberships."""
    # Composite index — covers WHERE doc_id = X AND status = Y queries used by
    # pending_count sub-queries and the consolidation/review service functions.
    op.create_index(
        "ix_amendments_doc_status",
        "amendments",
        ["doc_id", "status"],
    )

    # Single-column index — covers status-only filters used by admin dashboards.
    op.create_index(
        "ix_amendments_status",
        "amendments",
        ["status"],
    )

    # Composite index — covers WHERE org_id = X AND role = Y lookups used by
    # _require_membership owner/admin checks on every protected endpoint.
    op.create_index(
        "ix_memberships_org_role",
        "memberships",
        ["org_id", "role"],
    )


def downgrade() -> None:
    """Drop the performance indexes added in this revision."""
    op.drop_index("ix_memberships_org_role", table_name="memberships")
    op.drop_index("ix_amendments_status", table_name="amendments")
    op.drop_index("ix_amendments_doc_status", table_name="amendments")
