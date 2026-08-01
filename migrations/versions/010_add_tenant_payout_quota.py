"""add_tenant_payout_quota (tenants.payout_limit/payout_used)

Revision ID: 010_add_tenant_payout_quota
Revises: 009_add_tenant_status
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_add_tenant_payout_quota"
down_revision: Union[str, None] = "009_add_tenant_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("tenants"):
        cols = [c["name"] for c in sa.inspect(bind).get_columns("tenants")]
        if "payout_limit" not in cols:
            op.execute("ALTER TABLE tenants ADD COLUMN payout_limit FLOAT NOT NULL DEFAULT 0.0")
        if "payout_used" not in cols:
            op.execute("ALTER TABLE tenants ADD COLUMN payout_used FLOAT NOT NULL DEFAULT 0.0")


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("tenants"):
        cols = [c["name"] for c in sa.inspect(bind).get_columns("tenants")]
        if "payout_used" in cols:
            op.execute("ALTER TABLE tenants DROP COLUMN payout_used")
        if "payout_limit" in cols:
            op.execute("ALTER TABLE tenants DROP COLUMN payout_limit")
