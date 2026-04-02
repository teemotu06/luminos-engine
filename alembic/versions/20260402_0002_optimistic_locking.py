"""add optimistic locking columns for lesson writes

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02 15:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if _has_table(inspector, "lesson_attempt"):
        columns = _column_names(inspector, "lesson_attempt")
        with op.batch_alter_table("lesson_attempt") as batch_op:
            if "version" not in columns:
                batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    if _has_table(inspector, "slide_result"):
        columns = _column_names(inspector, "slide_result")
        with op.batch_alter_table("slide_result") as batch_op:
            if "version" not in columns:
                batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    raise RuntimeError("Downgrade is not supported for optimistic locking migration.")
