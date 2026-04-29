"""create core tables

Revision ID: 0001
Revises:
Create Date: 2026-03-21 00:00:00.000000

Reason for change: Initial schema — creates the four core domain tables
(users, organisations, memberships, documents) needed for user authentication,
organisation workspaces, role-based access control, and document management.
This is the foundation every subsequent migration will build upon.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users, organisations, memberships, and documents tables."""

    # ------------------------------------------------------------------
    # ENUM types — use PL/pgSQL DO blocks to create idempotently.
    # Direct op.execute() bypasses the SQLAlchemy asyncpg ORM event hooks
    # that re-create types inside create_table() despite create_type=False.
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE user_plan AS ENUM ('free', 'pro', 'enterprise');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE org_plan AS ENUM ('free', 'pro', 'enterprise');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE document_status AS ENUM ('draft', 'open', 'closed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE amendment_status AS ENUM ('pending', 'accepted', 'rejected', 'withdrawn');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column(
            "plan",
            postgresql.ENUM(name="user_plan", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # organisations
    # ------------------------------------------------------------------
    op.create_table(
        "organisations",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column(
            "plan",
            postgresql.ENUM(name="org_plan", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_organisations_slug"),
    )
    op.create_index("ix_organisations_slug", "organisations", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # memberships  (composite PK: user_id + org_id)
    # ------------------------------------------------------------------
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "role",
            postgresql.ENUM(name="member_role", create_type=False),
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="document_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_documents_org_id", "documents", ["org_id"])

    # ------------------------------------------------------------------
    # amendments
    # ------------------------------------------------------------------
    op.create_table(
        "amendments",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(500), nullable=True),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("proposed_text", sa.Text, nullable=False),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="amendment_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_amendments_doc_id", "amendments", ["doc_id"])
    op.create_index("ix_amendments_author_id", "amendments", ["author_id"])


def downgrade() -> None:
    """Drop all core tables and their enum types in reverse dependency order."""

    op.drop_table("amendments")
    op.drop_table("documents")
    op.drop_table("memberships")
    op.drop_table("organisations")
    op.drop_table("users")

    # Drop enum types after tables that use them are gone
    op.execute("DROP TYPE IF EXISTS amendment_status")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS member_role")
    op.execute("DROP TYPE IF EXISTS org_plan")
    op.execute("DROP TYPE IF EXISTS user_plan")
