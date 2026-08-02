"""add_tenant_owner (tenants.owner_id)

I2 修复：租户写操作 owner 校验（资金管控层授权）。

Revision ID: 015_add_tenant_owner
Revises: 014_add_maintenance_windows
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_add_tenant_owner"
down_revision: Union[str, None] = "014_add_maintenance_windows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    insp = sa.inspect(bind)
    if bind is not None and insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "owner_id" not in cols:
            op.execute("ALTER TABLE tenants ADD COLUMN owner_id VARCHAR(128)")
        if "ix_tenants_owner_id" not in {ix["name"] for ix in insp.get_indexes("tenants")}:
            op.create_index("ix_tenants_owner_id", "tenants", ["owner_id"])


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    insp = sa.inspect(bind)
    if bind is not None and insp.has_table("tenants"):
        if "ix_tenants_owner_id" in {ix["name"] for ix in insp.get_indexes("tenants")}:
            op.drop_index("ix_tenants_owner_id", table_name="tenants")
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "owner_id" in cols:
            op.execute("ALTER TABLE tenants DROP COLUMN owner_id")
