"""Офферы потоков для редактора существующих кампаний

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("keitaro_share", sa.Integer(), nullable=True),
        sa.Column("was_in_keitaro", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stream_id", "offer_id", name="uq_stream_offers_stream_offer"),
    )
    op.create_index("ix_stream_offers_campaign_id", "stream_offers", ["campaign_id"])
    op.create_index("ix_stream_offers_stream_id", "stream_offers", ["stream_id"])


def downgrade() -> None:
    op.drop_index("ix_stream_offers_stream_id", table_name="stream_offers")
    op.drop_index("ix_stream_offers_campaign_id", table_name="stream_offers")
    op.drop_table("stream_offers")
