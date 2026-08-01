"""add_slo_snapshots (slo_snapshots table)

Revision ID: 011_add_slo_snapshots
Revises: 010_add_tenant_payout_quota
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_add_slo_snapshots"
down_revision: Union[str, None] = "010_add_tenant_payout_quota"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and not sa.inspect(bind).has_table("slo_snapshots"):
        op.create_table(
            "slo_snapshots",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("slo_name", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="healthy"),
            sa.Column("remaining_pct", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("sampled_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_slo_snapshots_slo_name", "slo_snapshots", ["slo_name"])
        op.create_index("ix_slo_snapshots_sampled_at", "slo_snapshots", ["sampled_at"])


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("slo_snapshots"):
        op.drop_table("slo_snapshots")
