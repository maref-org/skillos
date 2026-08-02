"""add_deposit_status_and_compliance (outcome_contracts.deposit_status + evidence/arbitration)

Revision ID: 006_add_deposit_status
Revises: 005_add_outcome_contracts
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_add_deposit_status"
down_revision: Union[str, None] = "005_add_outcome_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None:
        insp = sa.inspect(bind)
        if insp.has_table("outcome_contracts"):
            cols = {c["name"] for c in insp.get_columns("outcome_contracts")}
            if "deposit_status" not in cols:
                op.add_column(
                    "outcome_contracts",
                    sa.Column("deposit_status", sa.String(16), nullable=False, server_default="held"),
                )
            if "evidence_hash" not in cols:
                op.add_column(
                    "outcome_contracts",
                    sa.Column("evidence_hash", sa.String(64), nullable=True),
                )
            if "evidence_risk" not in cols:
                op.add_column(
                    "outcome_contracts",
                    sa.Column("evidence_risk", sa.Float(), nullable=True),
                )


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None:
        op.drop_column("outcome_contracts", "evidence_risk")
        op.drop_column("outcome_contracts", "evidence_hash")
        op.drop_column("outcome_contracts", "deposit_status")
