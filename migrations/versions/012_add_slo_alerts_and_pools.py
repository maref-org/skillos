"""add_slo_alerts_and_pools (slo_alerts + tenant_pools + pool members/adjustments)

Revision ID: 012_add_slo_alerts_and_pools
Revises: 011_add_slo_snapshots
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_add_slo_alerts_and_pools"
down_revision: Union[str, None] = "011_add_slo_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is None:
        return
    insp = sa.inspect(bind)
    if not insp.has_table("slo_alerts"):
        op.create_table(
            "slo_alerts",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("slo_name", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="firing"),
            sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
            sa.Column("remaining_pct", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        )
        op.create_index("ix_slo_alerts_slo_name", "slo_alerts", ["slo_name"])
    if not insp.has_table("tenant_pools"):
        op.create_table(
            "tenant_pools",
            sa.Column("pool_id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(256), nullable=False, server_default=""),
            sa.Column("total_limit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("used", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(16), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if not insp.has_table("tenant_pool_members"):
        op.create_table(
            "tenant_pool_members",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("pool_id", sa.String(64), nullable=False),
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("share_ratio", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_tenant_pool_members_pool_id", "tenant_pool_members", ["pool_id"])
        op.create_index("ix_tenant_pool_members_tenant_id", "tenant_pool_members", ["tenant_id"])
    if not insp.has_table("pool_adjustments"):
        op.create_table(
            "pool_adjustments",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("pool_id", sa.String(64), nullable=False),
            sa.Column("new_limit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("requested_by", sa.String(128), nullable=False, server_default=""),
            sa.Column("approved_by", sa.String(128), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_pool_adjustments_pool_id", "pool_adjustments", ["pool_id"])


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is None:
        return
    insp = sa.inspect(bind)
    for table in ("pool_adjustments", "tenant_pool_members", "tenant_pools", "slo_alerts"):
        if insp.has_table(table):
            op.drop_table(table)
