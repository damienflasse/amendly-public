"""add invitations table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-21 00:00:00.000000

Reason for change: Adds the invitations table to support the member invite flow.
An invitation records the target email, a unique URL-safe token, and an
expiry timestamp. When an invitee accepts the invite via the token link, the
service creates a Membership row and stamps accepted_at. This approach lets
owners/admins invite people who do not yet have an Amendly account, as well
as existing users.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the invitations table."""

    op.create_table(
        "invitations",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_invitations_token"),
    )
    op.create_index("ix_invitations_org_id", "invitations", ["org_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)


def downgrade() -> None:
    """Drop the invitations table."""

    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_index("ix_invitations_org_id", table_name="invitations")
    op.drop_table("invitations")
