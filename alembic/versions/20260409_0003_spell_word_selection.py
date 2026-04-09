"""add spell word selection state to class_session

Revision ID: 20260409_0003
Revises: 20260409_0002
Create Date: 2026-04-09 19:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0003"
down_revision = "20260409_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.add_column(sa.Column("spell_word_selection", sa.JSON(), nullable=False, server_default="[]"))
            batch_op.add_column(sa.Column("spell_word_slide_id", sa.String(64), nullable=True))
    else:
        op.add_column("class_session", sa.Column("spell_word_selection", sa.JSON(), nullable=False, server_default="[]"))
        op.add_column("class_session", sa.Column("spell_word_slide_id", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "sqlite":
        with op.batch_alter_table("class_session") as batch_op:
            batch_op.drop_column("spell_word_slide_id")
            batch_op.drop_column("spell_word_selection")
    else:
        op.drop_column("class_session", "spell_word_slide_id")
        op.drop_column("class_session", "spell_word_selection")
