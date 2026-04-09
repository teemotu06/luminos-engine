"""add class_session control plane table

Revision ID: 20260408_0001
Revises: 20260403_0001
Create Date: 2026-04-08 16:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "20260408_0001"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "class_session" in inspector.get_table_names():
        return

    dialect_name = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect_name == "postgresql" else sa.String(length=36)

    op.create_table(
        "class_session",
        sa.Column("class_id", uuid_type, sa.ForeignKey("class_group.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("lesson_id", sa.String(length=20), sa.ForeignKey("lesson.lesson_id"), nullable=True),
        sa.Column("attempt_id", uuid_type, sa.ForeignKey("lesson_attempt.attempt_id", ondelete="SET NULL"), nullable=True),
        sa.Column("current_slide_id", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_message", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("class_session")
