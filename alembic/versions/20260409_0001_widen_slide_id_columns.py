"""widen runtime slide_id columns for generated slide identifiers

Revision ID: 20260409_0001
Revises: 20260408_0001
Create Date: 2026-04-09 12:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0001"
down_revision = "20260408_0001"
branch_labels = None
depends_on = None


SLIDE_ID_COLUMNS = [
    ("class_session", "current_slide_id"),
    ("lesson_attempt", "current_slide_id"),
    ("slide_result", "slide_id"),
    ("student_mark", "slide_id"),
    ("oral_check_session", "slide_id"),
    ("oral_check_assignment", "slide_id"),
    ("lesson_runtime_state", "slide_id"),
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    for table_name, column_name in SLIDE_ID_COLUMNS:
        if dialect_name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.String(length=20),
                    type_=sa.String(length=64),
                    existing_nullable=True if column_name == "current_slide_id" else False,
                )
        else:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(length=20),
                type_=sa.String(length=64),
                existing_nullable=True if column_name == "current_slide_id" else False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    for table_name, column_name in reversed(SLIDE_ID_COLUMNS):
        if dialect_name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.String(length=64),
                    type_=sa.String(length=20),
                    existing_nullable=True if column_name == "current_slide_id" else False,
                )
        else:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(length=64),
                type_=sa.String(length=20),
                existing_nullable=True if column_name == "current_slide_id" else False,
            )
