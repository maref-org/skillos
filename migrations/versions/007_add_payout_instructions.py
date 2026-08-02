"""add_payout_instructions (payout_instructions)

Revision ID: 007_add_payout_instructions
Revises: 006_add_deposit_status
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_add_payout_instructions"
down_revision: Union[str, None] = "006_add_deposit_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is None or not sa.inspect(bind).has_table("payout_instructions"):
        op.create_table(
            "payout_instructions",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("contract_id", sa.String(64), nullable=False),
            sa.Column("payee_id", sa.String(128), nullable=False),
            sa.Column("role", sa.String(32), nullable=False, server_default="contractor"),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
            sa.Column("source", sa.String(16), nullable=False, server_default="settlement"),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("external_ref", sa.String(128), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["contract_id"], ["outcome_contracts.id"]),
        )
        op.create_index("ix_payout_instructions_contract_id", "payout_instructions", ["contract_id"])
        op.create_index("ix_payout_instructions_payee_id", "payout_instructions", ["payee_id"])


def downgrade() -> None:
    op.drop_table("payout_instructions")
