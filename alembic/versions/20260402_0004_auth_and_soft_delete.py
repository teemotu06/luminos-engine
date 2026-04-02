"""add auth users, class ownership, and soft delete

Revision ID: 20260402_0004
Revises: 20260402_0003
Create Date: 2026-04-02 17:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql


revision = "20260402_0004"
down_revision = "20260402_0003"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name, column_name):
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _fk_names(inspector, table_name):
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    dialect_name = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=True) if dialect_name == "postgresql" else sa.String(length=36)

    if not _has_table(inspector, "app_user"):
        op.create_table(
            "app_user",
            sa.Column("id", uuid_type, primary_key=True, nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="teacher"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_app_user_username", "app_user", ["username"], unique=True)

    inspector = inspect(bind)
    if not _has_table(inspector, "class_group"):
        return

    if not _has_column(inspector, "class_group", "owner_user_id"):
        with op.batch_alter_table("class_group", recreate="auto") as batch_op:
            batch_op.add_column(sa.Column("owner_user_id", uuid_type, nullable=True))
            batch_op.create_index("ix_class_group_owner_user_id", ["owner_user_id"], unique=False)

    inspector = inspect(bind)
    if not _has_column(inspector, "class_group", "deleted_at"):
        with op.batch_alter_table("class_group", recreate="auto") as batch_op:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))

    inspector = inspect(bind)
    fk_name = "fk_class_group_owner_user_id"
    if fk_name not in _fk_names(inspector, "class_group"):
        with op.batch_alter_table("class_group", recreate="auto") as batch_op:
            batch_op.create_foreign_key(
                fk_name,
                "app_user",
                ["owner_user_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if dialect_name == "postgresql":
        bind.execute(text("ALTER TABLE app_user ALTER COLUMN role DROP DEFAULT"))


def downgrade():
    raise RuntimeError("Downgrade is not supported for auth and soft delete migration.")
