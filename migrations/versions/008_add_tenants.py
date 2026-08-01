"""add_tenants (tenants + outcome_contracts.tenant_id)

Revision ID: 008_add_tenants
Revises: 007_add_payout_instructions
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_add_tenants"
down_revision: Union[str, None] = "007_add_payout_instructions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is None or not sa.inspect(bind).has_table("tenants"):
        op.create_table(
            "tenants",
            sa.Column("tenant_id", sa.String(128), nullable=False),
            sa.Column("name", sa.String(256), nullable=False, server_default=""),
            sa.Column("scene_config", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("tenant_id"),
        )
    op.execute(
        "ALTER TABLE outcome_contracts ADD COLUMN tenant_id VARCHAR(128)"
    )
    op.create_index("ix_outcome_contracts_tenant_id", "outcome_contracts", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_outcome_contracts_tenant_id", table_name="outcome_contracts")
    op.drop_table("tenants")
