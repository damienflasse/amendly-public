"""add withdrawn value to amendment_status enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-22 00:00:00.000000

Reason for change: Adds the 'withdrawn' value to the amendment_status PostgreSQL
enum type.  A withdrawn amendment is one that the author has chosen to retract.
The row is kept in the database (soft-delete) with status='withdrawn' so that
history is preserved.  Only pending amendments may be withdrawn, and only by
their author.  SQLite (used in tests) does not require ALTER TYPE so the
migration is a no-op there.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'withdrawn' to the amendment_status enum (PostgreSQL only)."""
    # SQLite does not have ALTER TYPE; the guard skips it in test environments.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE amendment_status ADD VALUE IF NOT EXISTS 'withdrawn'")


def downgrade() -> None:
    """Removing an enum value from PostgreSQL is not straightforward.

    To downgrade, first ensure no rows have status='withdrawn', then recreate
    the enum without that value and update the column.  For now this is left
    as a manual operation — automated rollback is not provided.
    """
    pass
