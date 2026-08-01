"""add_slo_alert_silence (slo_alerts.silenced_until)

Revision ID: 013_add_slo_alert_silence
Revises: 012_add_slo_alerts_and_pools
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_add_slo_alert_silence"
down_revision: Union[str, None] = "012_add_slo_alerts_and_pools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("slo_alerts"):
        cols = [c["name"] for c in sa.inspect(bind).get_columns("slo_alerts")]
        if "silenced_until" not in cols:
            op.execute("ALTER TABLE slo_alerts ADD COLUMN silenced_until DATETIME")


def downgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind
    if bind is not None and sa.inspect(bind).has_table("slo_alerts"):
        cols = [c["name"] for c in sa.inspect(bind).get_columns("slo_alerts")]
        if "silenced_until" in cols:
            op.execute("ALTER TABLE slo_alerts DROP COLUMN silenced_until")
