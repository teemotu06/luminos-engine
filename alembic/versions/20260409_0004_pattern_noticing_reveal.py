"""Add pattern_noticing reveal counters to class_session.

Revision ID: 20260409_0004
Revises: 20260409_0003
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0004"
down_revision = "20260409_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("class_session", sa.Column("pattern_noticing_reveal_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("class_session", sa.Column("pattern_noticing_slide_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("class_session", "pattern_noticing_slide_id")
    op.drop_column("class_session", "pattern_noticing_reveal_count")
