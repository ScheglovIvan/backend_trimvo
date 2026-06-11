"""add_preview_compressed_path_to_templates

Revision ID: 0006
Revises: e4d774550ce1
Create Date: 2026-06-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "e4d774550ce1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='templates' AND column_name='preview_compressed_path'"
    ))
    if not result.fetchone():
        op.add_column("templates", sa.Column("preview_compressed_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("templates", "preview_compressed_path")
