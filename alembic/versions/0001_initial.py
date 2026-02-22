"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("username", name="uq_admin_users_username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=False)

    op.create_table(
        "app_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("name", name="uq_app_types_name"),
        sa.UniqueConstraint("slug", name="uq_app_types_slug"),
    )
    op.create_index("ix_app_types_slug", "app_types", ["slug"], unique=False)

    op.create_table(
        "apk_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_type_id", sa.Integer(), sa.ForeignKey("app_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("release_note", sa.Text(), nullable=True),
        sa.Column("current_file_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("app_type_id", "version", name="uq_apk_versions_app_type_version"),
    )

    op.create_table(
        "apk_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("apk_version_id", sa.Integer(), sa.ForeignKey("apk_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("apk_version_id", "revision_no", name="uq_apk_files_version_revision"),
    )

    op.create_table(
        "notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "download_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("apk_file_id", sa.Integer(), sa.ForeignKey("apk_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("app_type_id", sa.Integer(), sa.ForeignKey("app_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("download_logs")
    op.drop_table("audit_logs")
    op.drop_table("notices")
    op.drop_table("apk_files")
    op.drop_table("apk_versions")
    op.drop_index("ix_app_types_slug", table_name="app_types")
    op.drop_table("app_types")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
