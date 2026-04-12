"""add public_holiday and course_plan tables for knowledge scheduling

Revision ID: 20260412_0001
Revises: 20260409_0005
Create Date: 2026-04-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0001"
down_revision = "20260409_0005"
branch_labels = None
depends_on = None

# Use the same UUID type as class_group.id — native UUID on Postgres, CHAR(36) elsewhere.
def _uuid_type(dialect_name: str):
    if dialect_name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.CHAR(36)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    uid = _uuid_type(dialect_name)

    # ── public_holiday ────────────────────────────────────────────────────────
    op.create_table(
        "public_holiday",
        sa.Column("id", uid, primary_key=True),
        sa.Column("holiday_date", sa.Date, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("holiday_date", "region", name="uq_holiday_date_region"),
    )
    op.create_index("ix_public_holiday_holiday_date", "public_holiday", ["holiday_date"])

    # ── course_plan ───────────────────────────────────────────────────────────
    op.create_table(
        "course_plan",
        sa.Column("id", uid, primary_key=True),
        sa.Column(
            "class_id",
            uid,
            sa.ForeignKey("class_group.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("curriculum_id", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("teaching_days", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("lesson_schedule", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_course_plan_class_id", "course_plan", ["class_id"])


def downgrade() -> None:
    op.drop_index("ix_course_plan_class_id", table_name="course_plan")
    op.drop_table("course_plan")
    op.drop_index("ix_public_holiday_holiday_date", table_name="public_holiday")
    op.drop_table("public_holiday")
