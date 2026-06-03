"""add_template_generation_fields

Revision ID: 0004
Revises: 51e34e804382
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004'
down_revision: Union[str, None] = '51e34e804382'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('templates', sa.Column('gems_cost', sa.Integer(), nullable=True, server_default='200'))
    op.add_column('templates', sa.Column('photo_slots', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('templates', sa.Column('has_male_slot', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('templates', sa.Column('has_female_slot', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('templates', 'has_female_slot')
    op.drop_column('templates', 'has_male_slot')
    op.drop_column('templates', 'photo_slots')
    op.drop_column('templates', 'gems_cost')
