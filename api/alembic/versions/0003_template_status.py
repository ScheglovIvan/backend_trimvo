"""add status to templates

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("templates", sa.Column("status", sa.String(20), nullable=True, server_default="ready"))


def downgrade():
    op.drop_column("templates", "status")
