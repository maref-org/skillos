"""add_provider_profiles_bounties (provider_profiles, bounties, bounty_applications)

Revision ID: 004_add_provider_profiles_bounties
Revises: 003_add_market_tables
Create Date: 2026-07-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_add_provider_profiles_bounties"
down_revision: Union[str, None] = "003_add_market_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context
    from sqlalchemy import inspect

    bind = get_context().bind

    if bind is None or not inspect(bind).has_table("provider_profiles"):
        op.create_table(
            "provider_profiles",
            sa.Column("provider_id", sa.String(128), nullable=False),
            sa.Column("role", sa.String(16), nullable=False, server_default="provider"),
            sa.Column("headline", sa.String(256), nullable=False, server_default=""),
            sa.Column("bio", sa.Text(), nullable=False, server_default=""),
            sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("categories", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("city", sa.String(128), nullable=False, server_default=""),
            sa.Column("country", sa.String(8), nullable=False, server_default=""),
            sa.Column("timezone", sa.String(64), nullable=False, server_default=""),
            sa.Column("is_remote_available", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("hourly_rate", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
            sa.Column("availability", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("gender", sa.String(16), nullable=True),
            sa.Column("phone", sa.String(32), nullable=True),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("profile_complete_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("is_profile_complete", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("total_bookings", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rating", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("activity_freshness", sa.String(32), nullable=False, server_default="new"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("provider_id"),
            sa.ForeignKeyConstraint(["provider_id"], ["identities.identity_id"]),
        )
        op.create_index("ix_provider_profiles_complete", "provider_profiles", ["is_profile_complete"])
        op.create_index("ix_provider_profiles_city", "provider_profiles", ["city"])

    if bind is None or not inspect(bind).has_table("bounties"):
        op.create_table(
            "bounties",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("poster_id", sa.String(128), nullable=False),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("completion_criteria", sa.Text(), nullable=False, server_default=""),
            sa.Column("evidence_types", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("price_type", sa.String(16), nullable=False, server_default="fixed"),
            sa.Column("price", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
            sa.Column("category", sa.String(64), nullable=False, server_default="general"),
            sa.Column("skill_tags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("city", sa.String(128), nullable=False, server_default=""),
            sa.Column("country", sa.String(8), nullable=False, server_default=""),
            sa.Column("is_remote_allowed", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("deadline", sa.DateTime(), nullable=True),
            sa.Column("spots_available", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("spots_filled", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("identity_required", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_bounties_poster_id", "bounties", ["poster_id"])
        op.create_index("ix_bounties_status", "bounties", ["status"])
        op.create_index("ix_bounties_category", "bounties", ["category"])
        op.create_index("ix_bounties_city", "bounties", ["city"])

    if bind is None or not inspect(bind).has_table("bounty_applications"):
        op.create_table(
            "bounty_applications",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("bounty_id", sa.String(64), nullable=False),
            sa.Column("applicant_id", sa.String(128), nullable=False),
            sa.Column("message", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("applied_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["bounty_id"], ["bounties.id"]),
            sa.ForeignKeyConstraint(
                ["applicant_id"],
                ["provider_profiles.provider_id"],
            ),
        )
        op.create_index("ix_bounty_applications_bounty_id", "bounty_applications", ["bounty_id"])
        op.create_index(
            "ix_bounty_applications_applicant_id",
            "bounty_applications",
            ["applicant_id"],
        )


def downgrade() -> None:
    op.drop_table("bounty_applications")
    op.drop_table("bounties")
    op.drop_table("provider_profiles")
