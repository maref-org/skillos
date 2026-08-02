"""add_outcome_contracts (reputations, outcome_contracts, service_teams, service_team_members, tips)

Revision ID: 005_add_outcome_contracts
Revises: 004_add_provider_profiles_bounties
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_add_outcome_contracts"
down_revision: Union[str, None] = "004_add_provider_profiles_bounties"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(bind, name: str) -> bool:
    from sqlalchemy import inspect

    return bind is None or not inspect(bind).has_table(name)


def upgrade() -> None:
    from alembic.context import get_context

    bind = get_context().bind

    if _has_table(bind, "reputations"):
        op.create_table(
            "reputations",
            sa.Column("entity_id", sa.String(128), nullable=False),
            sa.Column("entity_type", sa.String(16), nullable=False, server_default="agent"),
            sa.Column("total_actions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_rate", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("total_reviews", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("peer_reviews", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("governance_participation", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overall_score", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("entity_id"),
        )

    if _has_table(bind, "outcome_contracts"):
        op.create_table(
            "outcome_contracts",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("requester_id", sa.String(128), nullable=False),
            sa.Column("contractor_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("tier", sa.String(16), nullable=False, server_default="balanced"),
            sa.Column("requirement_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("deliverables", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("base_price", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("price", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
            sa.Column("deposit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("success_rate_commitment", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("deadline", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_outcome_contracts_requester_id", "outcome_contracts", ["requester_id"])
        op.create_index("ix_outcome_contracts_status", "outcome_contracts", ["status"])

    if _has_table(bind, "service_teams"):
        op.create_table(
            "service_teams",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("contract_id", sa.String(64), nullable=False),
            sa.Column("lead_id", sa.String(128), nullable=False, server_default=""),
            sa.Column("status", sa.String(16), nullable=False, server_default="assembling"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["contract_id"], ["outcome_contracts.id"]),
        )
        op.create_index("ix_service_teams_contract_id", "service_teams", ["contract_id"])

    if _has_table(bind, "service_team_members"):
        op.create_table(
            "service_team_members",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("team_id", sa.String(64), nullable=False),
            sa.Column("member_id", sa.String(128), nullable=False),
            sa.Column("role", sa.String(32), nullable=False, server_default="skill_author"),
            sa.Column("share_ratio", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["team_id"], ["service_teams.id"]),
        )
        op.create_index("ix_service_team_members_team_id", "service_team_members", ["team_id"])
        op.create_index("ix_service_team_members_member_id", "service_team_members", ["member_id"])

    if _has_table(bind, "tips"):
        op.create_table(
            "tips",
            sa.Column("id", sa.String(64), nullable=False),
            sa.Column("contract_id", sa.String(64), nullable=False),
            sa.Column("requester_id", sa.String(128), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("ratio", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("distributions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["contract_id"], ["outcome_contracts.id"]),
        )
        op.create_index("ix_tips_contract_id", "tips", ["contract_id"])
        op.create_index("ix_tips_requester_id", "tips", ["requester_id"])


def downgrade() -> None:
    op.drop_table("tips")
    op.drop_table("service_team_members")
    op.drop_table("service_teams")
    op.drop_table("outcome_contracts")
    op.drop_table("reputations")
