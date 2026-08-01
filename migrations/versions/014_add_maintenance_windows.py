"""add_maintenance_windows (maintenance_windows 表)

Revision ID: 014_add_maintenance_windows
Revises: 013_add_slo_alert_silence
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_add_maintenance_windows"
down_revision: Union[str, None] = "013_add_slo_alert_silence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and not sa.inspect(bind).has_table("maintenance_windows"):
        op.create_table(
            "maintenance_windows",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("slo_name", sa.String(64), nullable=False, server_default="*"),
            sa.Column("cron_expression", sa.String(128), nullable=False),
            sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("description", sa.String(256), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_maintenance_windows_slo_name", "maintenance_windows", ["slo_name"])


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("maintenance_windows"):
        op.drop_table("maintenance_windows")
