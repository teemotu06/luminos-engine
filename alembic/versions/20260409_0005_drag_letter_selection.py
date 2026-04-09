"""add drag letter selection state to class_session

Revision ID: 20260409_0005
Revises: 20260409_0004
Create Date: 2026-04-09 22:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0005"
down_revision = "20260409_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.add_column(sa.Column("drag_letter_selection", sa.JSON(), nullable=False, server_default="[]"))
            batch_op.add_column(sa.Column("drag_letter_slide_id", sa.String(64), nullable=True))
    else:
        op.add_column("class_session", sa.Column("drag_letter_selection", sa.JSON(), nullable=False, server_default="[]"))
        op.add_column("class_session", sa.Column("drag_letter_slide_id", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.drop_column("drag_letter_slide_id")
            batch_op.drop_column("drag_letter_selection")
    else:
        op.drop_column("class_session", "drag_letter_slide_id")
        op.drop_column("class_session", "drag_letter_selection")
