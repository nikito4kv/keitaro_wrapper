"""Первые таблицы: настройки по умолчанию и журнал созданных кампаний

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_defaults",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=False),
        sa.Column("domain_url", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("traffic_source_id", sa.Integer(), nullable=False),
        sa.Column("traffic_source_name", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "created_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keitaro_campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("alias", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("countries", sa.JSON(), nullable=False),
        sa.Column("redirect_url", sa.String(length=512), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("offer_name", sa.String(length=255), nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=False),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("traffic_source_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_created_campaigns_keitaro_campaign_id", "created_campaigns", ["keitaro_campaign_id"])
    op.create_index("ix_created_campaigns_created_at", "created_campaigns", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_created_campaigns_created_at", table_name="created_campaigns")
    op.drop_index("ix_created_campaigns_keitaro_campaign_id", table_name="created_campaigns")
    op.drop_table("created_campaigns")
    op.drop_table("campaign_defaults")
