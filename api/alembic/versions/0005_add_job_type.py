"""add_job_type_to_jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column(
        'job_type',
        sa.String(20),
        nullable=False,
        server_default='template',
    ))


def downgrade() -> None:
    op.drop_column('jobs', 'job_type')
