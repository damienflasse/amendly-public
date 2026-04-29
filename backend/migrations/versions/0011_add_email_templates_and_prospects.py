"""Add email_templates and prospects tables.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-25 00:00:00.000000

Reason for change:
  1. email_templates — superadmin-editable transactional email templates.
     Each row stores a unique template_key (e.g. 'invite', 'amendment_accepted'),
     a subject line, and an html_body with {variable} placeholders.
     If no row exists for a key, the hardcoded fallback in code is used.

  2. prospects — mini-CRM table for tracking sales leads.
     Stores contact details, pipeline status, and free-text notes visible
     only to the superadmin.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- email_templates -------------------------------------------------------
    op.create_table(
        "email_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_key", sa.String(64), nullable=False, unique=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("html_body", sa.Text, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- prospects -------------------------------------------------------------
    op.create_table(
        "prospects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("org_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_prospects_email", "prospects", ["email"])


def downgrade() -> None:
    op.drop_index("ix_prospects_email", table_name="prospects")
    op.drop_table("prospects")
    op.drop_table("email_templates")
