"""rename plan enum values: free→solo, pro→team, enterprise→organisation

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-22 00:00:00.000000

Reason for change: The product pricing was redesigned from a two-tier (Free/Pro)
model to three paid tiers (Solo/Team/Organisation). This migration renames the
existing PostgreSQL enum values to match the new plan names, and updates the
DEFAULT constraints on the organisations.plan and users.plan columns to point to
the new 'solo' value.

SQLite note: ALTER TYPE is a PostgreSQL-only feature. The guard below ensures the
migration is a no-op in SQLite (used by the test suite).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename enum values in org_plan and user_plan types (PostgreSQL only).
    Update DEFAULT constraints on organisations.plan and users.plan.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite / other dialects: no-op

    # org_plan enum
    op.execute("ALTER TYPE org_plan RENAME VALUE 'free' TO 'solo'")
    op.execute("ALTER TYPE org_plan RENAME VALUE 'pro' TO 'team'")
    op.execute("ALTER TYPE org_plan RENAME VALUE 'enterprise' TO 'organisation'")

    # user_plan enum
    op.execute("ALTER TYPE user_plan RENAME VALUE 'free' TO 'solo'")
    op.execute("ALTER TYPE user_plan RENAME VALUE 'pro' TO 'team'")
    op.execute("ALTER TYPE user_plan RENAME VALUE 'enterprise' TO 'organisation'")

    # Update column DEFAULTs
    op.execute(
        "ALTER TABLE organisations ALTER COLUMN plan SET DEFAULT 'solo'::org_plan"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN plan SET DEFAULT 'solo'::user_plan"
    )


def downgrade() -> None:
    """
    Rename enum values back to original names (PostgreSQL only).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # org_plan enum
    op.execute("ALTER TYPE org_plan RENAME VALUE 'solo' TO 'free'")
    op.execute("ALTER TYPE org_plan RENAME VALUE 'team' TO 'pro'")
    op.execute("ALTER TYPE org_plan RENAME VALUE 'organisation' TO 'enterprise'")

    # user_plan enum
    op.execute("ALTER TYPE user_plan RENAME VALUE 'solo' TO 'free'")
    op.execute("ALTER TYPE user_plan RENAME VALUE 'team' TO 'pro'")
    op.execute("ALTER TYPE user_plan RENAME VALUE 'organisation' TO 'enterprise'")

    # Restore column DEFAULTs
    op.execute(
        "ALTER TABLE organisations ALTER COLUMN plan SET DEFAULT 'free'::org_plan"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN plan SET DEFAULT 'free'::user_plan"
    )
