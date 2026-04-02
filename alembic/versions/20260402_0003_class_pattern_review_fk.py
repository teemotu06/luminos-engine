"""enforce class_pattern_review class foreign key

Revision ID: 20260402_0003
Revises: 20260402_0002
Create Date: 2026-04-02 15:35:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql


revision = "20260402_0003"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


FK_NAME = "fk_class_pattern_review_class_id"


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _fk_names(inspector, table_name):
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if not (_has_table(inspector, "class_pattern_review") and _has_table(inspector, "class_group")):
        return

    if bind.dialect.name == "postgresql":
        # Legacy Postgres databases stored class_pattern_review.class_id as VARCHAR
        # while class_group.id is UUID. Clean bad rows, then align the type.
        bind.execute(
            text(
                """
                DELETE FROM class_pattern_review
                WHERE class_id IS NULL
                   OR class_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                   OR class_id NOT IN (SELECT CAST(id AS text) FROM class_group)
                """
            )
        )
        class_id_column = next(
            (column for column in inspector.get_columns("class_pattern_review") if column["name"] == "class_id"),
            None,
        )
        if class_id_column is not None and not isinstance(class_id_column["type"], postgresql.UUID):
            op.alter_column(
                "class_pattern_review",
                "class_id",
                existing_type=class_id_column["type"],
                type_=postgresql.UUID(as_uuid=True),
                postgresql_using="class_id::uuid",
            )
    else:
        bind.execute(
            text(
                """
                DELETE FROM class_pattern_review
                WHERE class_id NOT IN (SELECT id FROM class_group)
                """
            )
        )

    if FK_NAME in _fk_names(inspector, "class_pattern_review"):
        return

    with op.batch_alter_table("class_pattern_review", recreate="auto") as batch_op:
        batch_op.create_foreign_key(
            FK_NAME,
            "class_group",
            ["class_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade():
    raise RuntimeError("Downgrade is not supported for class_pattern_review FK migration.")
