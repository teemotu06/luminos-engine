"""baseline schema and legacy upgrades

Revision ID: 20260402_0001
Revises:
Create Date: 2026-04-02 13:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260402_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name):
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector, table_name):
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _sqlite_json_type(bind):
    return sa.JSON() if bind.dialect.name == "sqlite" else sa.JSON()


def _uuid_type(bind):
    return sa.String(length=36) if bind.dialect.name == "sqlite" else sa.UUID(as_uuid=True)


def _create_missing_tables(bind, inspector):
    json_type = _sqlite_json_type(bind)
    uuid_type = _uuid_type(bind)
    if not _has_table(inspector, "class_group"):
        op.create_table(
            "class_group",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("class_name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not _has_table(inspector, "lesson"):
        op.create_table(
            "lesson",
            sa.Column("lesson_id", sa.String(length=20), primary_key=True, nullable=False),
            sa.Column("unit_id", sa.String(length=10), nullable=False),
            sa.Column("target_pattern", sa.String(length=50), nullable=False),
            sa.Column("content_pack_status", sa.String(length=20), nullable=False),
            sa.Column("json_path", sa.String(length=200), nullable=False),
        )

    if not _has_table(inspector, "student_record"):
        op.create_table(
            "student_record",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("class_id", uuid_type, nullable=False),
            sa.Column("student_name", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["class_group.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("class_id", "student_name", name="uq_student_per_class"),
        )

    if not _has_table(inspector, "lesson_attempt"):
        op.create_table(
            "lesson_attempt",
            sa.Column("attempt_id", uuid_type, primary_key=True, nullable=False),
            sa.Column("lesson_id", sa.String(length=20), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=True),
            sa.Column("learner_key", sa.String(length=64), nullable=True),
            sa.Column("teacher_key", sa.String(length=64), nullable=True),
            sa.Column("attempt_date", sa.DateTime(), nullable=False),
            sa.Column("completed", sa.Boolean(), nullable=False),
            sa.Column("current_slide_id", sa.String(length=20), nullable=True),
            sa.Column("mastery_status", sa.String(length=20), nullable=False),
            sa.Column("phoneme_error_log", json_type, nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("next_recommendation", sa.String(length=20), nullable=False),
            sa.ForeignKeyConstraint(["lesson_id"], ["lesson.lesson_id"]),
        )

    if not _has_table(inspector, "slide_result"):
        op.create_table(
            "slide_result",
            sa.Column("result_id", uuid_type, primary_key=True, nullable=False),
            sa.Column("attempt_id", uuid_type, nullable=False),
            sa.Column("slide_id", sa.String(length=20), nullable=False),
            sa.Column("block_id", sa.String(length=2), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error_tags", json_type, nullable=False),
            sa.Column("korean_transfer", sa.Boolean(), nullable=False),
            sa.Column("teacher_note", sa.Text(), nullable=True),
            sa.Column("item_results", json_type, nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempt.attempt_id"]),
        )

    if not _has_table(inspector, "student_mark"):
        op.create_table(
            "student_mark",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("attempt_id", uuid_type, nullable=False),
            sa.Column("lesson_id", sa.String(length=20), nullable=False),
            sa.Column("slide_id", sa.String(length=20), nullable=False),
            sa.Column("block_id", sa.String(length=2), nullable=False),
            sa.Column("student_name", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error_tags", json_type, nullable=True),
            sa.Column("support_level", sa.String(length=20), nullable=True),
            sa.Column("teacher_note", sa.Text(), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempt.attempt_id"]),
        )

    if not _has_table(inspector, "oral_check_session"):
        op.create_table(
            "oral_check_session",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("attempt_id", uuid_type, nullable=False),
            sa.Column("lesson_id", sa.String(length=20), nullable=False),
            sa.Column("slide_id", sa.String(length=20), nullable=False),
            sa.Column("block_id", sa.String(length=2), nullable=False),
            sa.Column("participation_mode", sa.String(length=40), nullable=False),
            sa.Column("audit_selection_strategy", sa.String(length=40), nullable=False, server_default="roster_order"),
            sa.Column("text_length_mode", sa.String(length=20), nullable=False, server_default="normal"),
            sa.Column("required_evidence_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("roster_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("required_student_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("resolved_student_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unresolved_student_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("session_status", sa.String(length=20), nullable=False, server_default="in_progress"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempt.attempt_id"]),
            sa.UniqueConstraint("attempt_id", "slide_id", name="uq_oral_check_session_attempt_slide"),
        )

    if not _has_table(inspector, "oral_check_assignment"):
        op.create_table(
            "oral_check_assignment",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("session_id", uuid_type, nullable=False),
            sa.Column("attempt_id", uuid_type, nullable=False),
            sa.Column("lesson_id", sa.String(length=20), nullable=False),
            sa.Column("slide_id", sa.String(length=20), nullable=False),
            sa.Column("block_id", sa.String(length=2), nullable=False),
            sa.Column("student_name", sa.String(length=100), nullable=False),
            sa.Column("performance_type", sa.String(length=40), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("queue_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("requires_reteach", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("resolved_in_block", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("teacher_note", sa.Text(), nullable=True),
            sa.Column("override_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["oral_check_session.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempt.attempt_id"]),
        )

    if not _has_table(inspector, "lesson_runtime_state"):
        op.create_table(
            "lesson_runtime_state",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("attempt_id", uuid_type, nullable=False),
            sa.Column("slide_id", sa.String(length=20), nullable=False),
            sa.Column("block_id", sa.String(length=2), nullable=False),
            sa.Column("current_state", sa.String(length=40), nullable=False, server_default="idle"),
            sa.Column("state_sequence", json_type, nullable=False),
            sa.Column("state_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("student_queue", json_type, nullable=False),
            sa.Column("queue_position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reteach_queue", json_type, nullable=False),
            sa.Column("current_student", sa.String(length=100), nullable=True),
            sa.Column("current_prompt_text", sa.Text(), nullable=True),
            sa.Column("teacher_prompt_text", sa.Text(), nullable=True),
            sa.Column("current_audio_url", sa.Text(), nullable=True),
            sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("audio_event_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ui_event_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["attempt_id"], ["lesson_attempt.attempt_id"], ondelete="CASCADE"),
            sa.UniqueConstraint("attempt_id", "slide_id", name="uq_lesson_runtime_attempt_slide"),
        )

    if not _has_table(inspector, "class_pattern_review"):
        op.create_table(
            "class_pattern_review",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("class_id", uuid_type, nullable=False),
            sa.Column("pattern_key", sa.String(length=100), nullable=False),
            sa.Column("source_lesson_id", sa.String(length=20), nullable=False),
            sa.Column("first_taught_lesson_id", sa.String(length=20), nullable=False),
            sa.Column("last_seen_lesson_id", sa.String(length=20), nullable=False),
            sa.Column("last_reviewed_lesson_id", sa.String(length=20), nullable=True),
            sa.Column("mastery_state", sa.String(length=20), nullable=False, server_default="shaky"),
            sa.Column("times_secure", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("times_shaky", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("times_missed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consecutive_weak_lessons", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("korean_transfer_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("weak_learner_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("marked_learner_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_due_lesson_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["class_group.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("class_id", "pattern_key", name="uq_class_pattern_review"),
        )


def _upgrade_existing_tables(bind, inspector):
    if _has_table(inspector, "lesson_attempt"):
        lesson_attempt_columns = _column_names(inspector, "lesson_attempt")
        with op.batch_alter_table("lesson_attempt") as batch_op:
            if "class_id" not in lesson_attempt_columns:
                batch_op.add_column(sa.Column("class_id", sa.String(length=36), nullable=True))
            if "current_slide_id" not in lesson_attempt_columns:
                batch_op.add_column(sa.Column("current_slide_id", sa.String(length=20), nullable=True))

    if _has_table(inspector, "oral_check_session"):
        oral_session_columns = _column_names(inspector, "oral_check_session")
        oral_session_uniques = _unique_constraint_names(inspector, "oral_check_session")
        with op.batch_alter_table("oral_check_session", recreate="auto") as batch_op:
            if "audit_selection_strategy" not in oral_session_columns:
                batch_op.add_column(
                    sa.Column(
                        "audit_selection_strategy",
                        sa.String(length=40),
                        nullable=False,
                        server_default="roster_order",
                    )
                )
            if "uq_oral_check_session_attempt_slide" not in oral_session_uniques:
                batch_op.create_unique_constraint(
                    "uq_oral_check_session_attempt_slide",
                    ["attempt_id", "slide_id"],
                )

    if _has_table(inspector, "lesson_runtime_state"):
        runtime_columns = _column_names(inspector, "lesson_runtime_state")
        with op.batch_alter_table("lesson_runtime_state") as batch_op:
            if "teacher_prompt_text" not in runtime_columns:
                batch_op.add_column(sa.Column("teacher_prompt_text", sa.Text(), nullable=True))


def _create_indexes(bind, inspector):
    index_specs = [
        ("lesson_attempt", "ix_lesson_attempt_class_id", ["class_id"]),
        ("slide_result", "ix_slide_result_attempt_slide", ["attempt_id", "slide_id"]),
        ("student_mark", "ix_student_mark_attempt_slide", ["attempt_id", "slide_id"]),
        ("student_mark", "ix_student_mark_student_name", ["student_name"]),
        ("class_pattern_review", "ix_class_pattern_review_class_id", ["class_id"]),
        ("oral_check_assignment", "ix_oral_check_assignment_session_id", ["session_id"]),
        ("oral_check_assignment", "ix_oral_check_assignment_student_name", ["student_name"]),
        ("lesson_runtime_state", "ix_lesson_runtime_state_attempt_id", ["attempt_id"]),
    ]
    for table_name, index_name, columns in index_specs:
        if not _has_table(inspector, table_name):
            continue
        if index_name not in _index_names(inspector, table_name):
            op.create_index(index_name, table_name, columns)


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    _create_missing_tables(bind, inspector)
    inspector = inspect(bind)
    _upgrade_existing_tables(bind, inspector)
    inspector = inspect(bind)
    _create_indexes(bind, inspector)


def downgrade():
    raise RuntimeError("Downgrade is not supported for the baseline migration.")
