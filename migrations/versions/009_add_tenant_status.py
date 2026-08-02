"""add_tenant_status (tenants.status)

Revision ID: 009_add_tenant_status
Revises: 008_add_tenants
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_add_tenant_status"
down_revision: Union[str, None] = "008_add_tenants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    insp = sa.inspect(bind)
    # C11 幂等修复：仅当列不存在才 ADD COLUMN
    if bind is not None and insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "status" not in cols:
            op.execute("ALTER TABLE tenants ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'draft'")


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    insp = sa.inspect(bind)
    if bind is not None and insp.has_table("tenants"):
        cols = {c["name"] for c in insp.get_columns("tenants")}
        if "status" in cols:
            op.execute("ALTER TABLE tenants DROP COLUMN status")
