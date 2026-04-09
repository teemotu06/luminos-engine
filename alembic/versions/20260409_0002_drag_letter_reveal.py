"""add letter reveal count to class_session

Revision ID: 20260409_0002
Revises: 20260409_0001
Create Date: 2026-04-09 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0002"
down_revision = "20260409_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.add_column(sa.Column("letter_reveal_count", sa.Integer(), nullable=True, server_default="0"))
            batch_op.add_column(sa.Column("letter_reveal_slide_id", sa.String(64), nullable=True))
    else:
        op.add_column("class_session", sa.Column("letter_reveal_count", sa.Integer(), nullable=True, server_default="0"))
        op.add_column("class_session", sa.Column("letter_reveal_slide_id", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.drop_column("letter_reveal_slide_id")
            batch_op.drop_column("letter_reveal_count")
    else:
        op.drop_column("class_session", "letter_reveal_slide_id")
        op.drop_column("class_session", "letter_reveal_count")
