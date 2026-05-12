"""Remove mock data from database

Revision ID: 005
Revises: 004
Create Date: 2025-05-12
"""
from alembic import op


# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Delete mock data in reverse dependency order
    tables = [
        'achievements',
        'announcements',
        'reactions',
        'quiz_submissions',
        'session_quizzes',
        'quiz_answers',
        'quiz_questions',
        'quizzes',
        'session_participants',
        'sessions',
        'lectures',
        'course_enrollments',
        'courses',
        'users'
    ]
    for table in tables:
        op.execute(f'DELETE FROM {table}')


def downgrade():
    # Re-run migration 002 to restore mock data
    pass
