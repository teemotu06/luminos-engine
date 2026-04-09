"""add student_outcomes to lesson_runtime_state

Revision ID: 20260403_0001
Revises: 20260402_0004
Create Date: 2026-04-03 09:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260403_0001"
down_revision = "20260402_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lesson_runtime_state",
        sa.Column(
            "student_outcomes",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("lesson_runtime_state", "student_outcomes")
