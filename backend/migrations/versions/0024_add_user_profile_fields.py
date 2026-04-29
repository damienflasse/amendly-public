"""Add company and job_position fields to users table.

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-02 00:00:00.000000

Reason for change:
  Users need to specify the company they work for and their job position so
  that other collaborators can easily identify who is editing an amendment.
  The existing avatar_url field already handles the profile picture.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company and job_position columns to the users table."""
    op.add_column(
        "users",
        sa.Column(
            "company",
            sa.String(255),
            nullable=True,
            comment="Organisation or company the user works for.",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "job_position",
            sa.String(255),
            nullable=True,
            comment="User's job title or role within their organisation.",
        ),
    )


def downgrade() -> None:
    """Drop company and job_position columns from the users table."""
    op.drop_column("users", "job_position")
    op.drop_column("users", "company")
