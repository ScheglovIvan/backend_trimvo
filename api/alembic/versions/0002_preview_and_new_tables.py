"""preview_path + reports, gem_packages, subscription_plans

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("templates", sa.Column("preview_path", sa.String(500), nullable=True))

    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "gem_packages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gems_amount", sa.Integer, nullable=False),
        sa.Column("bonus_gems", sa.Integer, server_default="0"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="UAH"),
        sa.Column("label", sa.String(100)),
        sa.Column("is_popular", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("apple_product_id", sa.String(200)),
        sa.Column("google_product_id", sa.String(200)),
        sa.Column("order", sa.Integer, server_default="0"),
    )

    op.create_table(
        "subscription_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100)),
        sa.Column("tier", sa.String(20)),
        sa.Column("period", sa.String(20)),
        sa.Column("price", sa.Numeric(10, 2)),
        sa.Column("currency", sa.String(10), server_default="UAH"),
        sa.Column("bonus_gems", sa.Integer, server_default="0"),
        sa.Column("discount_percent", sa.Integer, server_default="0"),
        sa.Column("apple_product_id", sa.String(200)),
        sa.Column("google_product_id", sa.String(200)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("order", sa.Integer, server_default="0"),
    )


def downgrade():
    op.drop_table("subscription_plans")
    op.drop_table("gem_packages")
    op.drop_table("reports")
    op.drop_column("templates", "preview_path")
