"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="user"),
        sa.Column("gems", sa.Integer, server_default="0"),
        sa.Column("subscription_status", sa.String(20), server_default="free"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("video_path", sa.String(500)),
        sa.Column("thumb_path", sa.String(500)),
        sa.Column("gif_path", sa.String(500)),
        sa.Column("likes", sa.Integer, server_default="0"),
        sa.Column("plays", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("order", sa.Integer, server_default="0"),
    )

    op.create_table(
        "category_templates",
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("order", sa.Integer, server_default="0"),
        sa.PrimaryKeyConstraint("category_id", "template_id"),
    )

    op.create_table(
        "trends",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id")),
        sa.Column("order", sa.Integer, server_default="0"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id")),
        sa.Column("status", sa.String(20), server_default="queued"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("result_path", sa.String(500)),
        sa.Column("error", sa.Text),
        sa.Column("options", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "admin_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100)),
        sa.Column("entity", sa.String(100)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("details", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("audit_log")
    op.drop_table("admin_config")
    op.drop_table("jobs")
    op.drop_table("trends")
    op.drop_table("category_templates")
    op.drop_table("categories")
    op.drop_table("templates")
    op.drop_table("users")
