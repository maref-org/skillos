"""add_market_tables (skill_listings, skill_reviews, settlements)

Revision ID: 003
Revises: 0015c682563a
Create Date: 2026-07-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_add_market_tables"
down_revision: Union[str, None] = "0015c682563a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context
    from sqlalchemy import inspect

    bind = get_context().bind

    if bind is None or not inspect(bind).has_table("skill_listings"):
        op.create_table(
            "skill_listings",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("skill_id", sa.String(64), nullable=False),
            sa.Column("name", sa.String(256), nullable=False),
            sa.Column("version", sa.String(32), nullable=False),
            sa.Column("author", sa.String(256), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("category", sa.String(64), nullable=False, server_default="general"),
            sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("price_per_call", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_revenue", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_skill_listings_skill_id", "skill_listings", ["skill_id"])
        op.create_index("ix_skill_listings_category", "skill_listings", ["category"])

    if bind is None or not inspect(bind).has_table("skill_reviews"):
        op.create_table(
            "skill_reviews",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("listing_id", sa.String(64), nullable=False),
            sa.Column("reviewer_id", sa.String(256), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("review_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["listing_id"], ["skill_listings.id"]),
        )
        op.create_index("ix_skill_reviews_listing_id", "skill_reviews", ["listing_id"])

    if bind is None or not inspect(bind).has_table("settlements"):
        op.create_table(
            "settlements",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("listing_id", sa.String(64), nullable=False),
            sa.Column("period", sa.String(32), nullable=False),
            sa.Column("total_amount", sa.Float(), nullable=False),
            sa.Column("platform_fee", sa.Float(), nullable=False),
            sa.Column("ecosystem_fee", sa.Float(), nullable=False),
            sa.Column("contributor_payout", sa.Float(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["listing_id"], ["skill_listings.id"]),
        )
        op.create_index("ix_settlements_listing_id", "settlements", ["listing_id"])
        op.create_index("ix_settlements_period", "settlements", ["period"])


def downgrade() -> None:
    op.drop_table("settlements")
    op.drop_table("skill_reviews")
    op.drop_table("skill_listings")
