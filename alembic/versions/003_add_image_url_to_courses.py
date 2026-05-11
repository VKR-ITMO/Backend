"""Add image_url to courses

Revision ID: 003
Revises: 002
Create Date: 2025-05-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('courses')]
    if 'image_url' not in columns:
        op.add_column('courses', sa.Column('image_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('courses', 'image_url')
