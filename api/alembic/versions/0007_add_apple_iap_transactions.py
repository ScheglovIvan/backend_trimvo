"""add_apple_iap_transactions

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apple_iap_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("transaction_id", sa.String(255), nullable=False, unique=True),
        sa.Column("original_transaction_id", sa.String(255), nullable=False),
        sa.Column("product_id", sa.String(255), nullable=False),
        sa.Column("purchase_type", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="processed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_apple_iap_transactions_original_transaction_id",
        "apple_iap_transactions",
        ["original_transaction_id"],
    )
    op.create_index(
        "ix_apple_iap_transactions_user_id",
        "apple_iap_transactions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_apple_iap_transactions_user_id", table_name="apple_iap_transactions")
    op.drop_index(
        "ix_apple_iap_transactions_original_transaction_id",
        table_name="apple_iap_transactions",
    )
    op.drop_table("apple_iap_transactions")
