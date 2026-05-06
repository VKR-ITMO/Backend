"""Fill db from CSV files

Revision ID: 002
Revises: 001
Create Date: 2026-04-06 12:00:00.000000

"""
from typing import Sequence, Union
from pathlib import Path
import csv
import uuid
import bcrypt
from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATA_DIR = Path(__file__).parent.parent / "test_data"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def read_csv(filename: str) -> list[dict]:
    """Читает CSV, чистит пустые строки, возвращает список словарей"""
    with open(DATA_DIR / filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [{k.strip(): (v.strip() if v.strip() != '' else None) for k, v in row.items()} for row in reader]


def upgrade() -> None:
    # 1. USERS (хешируем пароли на лету)
    users = read_csv('users.csv')
    for u in users:
        u['password_hash'] = hash_password(u.pop('password')) if u['password'] else None
        u['id'] = uuid.UUID(u['id'])

    op.bulk_insert(
        sa.table('users',
            sa.column('id', sa.UUID),
            sa.column('email', sa.String),
            sa.column('password_hash', sa.String),
            sa.column('full_name', sa.String),
            sa.column('avatar_url', sa.String),
            sa.column('role', sa.String),
            sa.column('created_at', sa.DateTime),
            sa.column('updated_at', sa.DateTime)
        ),
        users
    )

    # 2. COURSES
    courses = read_csv('courses.csv')
    for c in courses:
        c['id'] = uuid.UUID(c['id'])
        c['teacher_id'] = uuid.UUID(c['teacher_id'])

    op.bulk_insert(
        sa.table('courses',
            sa.column('id', sa.UUID),
            sa.column('teacher_id', sa.UUID),
            sa.column('name', sa.String),
            sa.column('code', sa.String),
            sa.column('description', sa.String),
            sa.column('semester', sa.String),
            sa.column('status', sa.String),
            sa.column('created_at', sa.DateTime)
        ),
        courses
    )

    # 3. COURSE ENROLLMENTS
    enrollments = read_csv('course_enrollments.csv')
    for e in enrollments:
        e['id'] = uuid.UUID(e['id'])
        e['course_id'] = uuid.UUID(e['course_id'])
        e['student_id'] = uuid.UUID(e['student_id'])

    op.bulk_insert(
        sa.table('course_enrollments',
            sa.column('id', sa.UUID),
            sa.column('course_id', sa.UUID),
            sa.column('student_id', sa.UUID),
            sa.column('enrolled_at', sa.DateTime)
        ),
        enrollments
    )

    # 4. LECTURES
    lectures = read_csv('lectures.csv')
    for l in lectures:
        l['id'] = uuid.UUID(l['id'])
        l['course_id'] = uuid.UUID(l['course_id'])
        l['teacher_id'] = uuid.UUID(l['teacher_id'])
        l['max_participants'] = int(l['max_participants']) if l['max_participants'] else None
        l['is_free_session'] = l['is_free_session'].lower() == 'true'

    op.bulk_insert(
        sa.table('lectures',
            sa.column('id', sa.UUID),
            sa.column('course_id', sa.UUID),
            sa.column('teacher_id', sa.UUID),
            sa.column('name', sa.String),
            sa.column('topic', sa.String),
            sa.column('description', sa.String),
            sa.column('scheduled_at', sa.DateTime),
            sa.column('status', sa.String),
            sa.column('access_code', sa.String),
            sa.column('max_participants', sa.Integer),
            sa.column('enabled_reactions', sa.JSON),
            sa.column('is_free_session', sa.Boolean)
        ),
        lectures
    )

    # 5. SESSIONS
    sessions = read_csv('sessions.csv')
    for s in sessions:
        s['id'] = uuid.UUID(s['id'])
        s['lecture_id'] = uuid.UUID(s['lecture_id'])
        s['teacher_id'] = uuid.UUID(s['teacher_id'])
        s['total_participants'] = int(s['total_participants'])
        s['total_reactions'] = int(s['total_reactions'])
        s['total_quizzes'] = int(s['total_quizzes'])

    op.bulk_insert(
        sa.table('sessions',
            sa.column('id', sa.UUID),
            sa.column('lecture_id', sa.UUID),
            sa.column('teacher_id', sa.UUID),
            sa.column('access_code', sa.String),
            sa.column('started_at', sa.DateTime),
            sa.column('ended_at', sa.DateTime),
            sa.column('total_participants', sa.Integer),
            sa.column('total_reactions', sa.Integer),
            sa.column('total_quizzes', sa.Integer)
        ),
        sessions
    )

    # 6. SESSION PARTICIPANTS
    participants = read_csv('session_participants.csv')
    for p in participants:
        p['id'] = uuid.UUID(p['id'])
        p['session_id'] = uuid.UUID(p['session_id'])
        p['student_id'] = uuid.UUID(p['student_id'])

    op.bulk_insert(
        sa.table('session_participants',
            sa.column('id', sa.UUID),
            sa.column('session_id', sa.UUID),
            sa.column('student_id', sa.UUID),
            sa.column('joined_at', sa.DateTime),
            sa.column('left_at', sa.DateTime)
        ),
        participants
    )

    # 7. QUIZZES
    quizzes = read_csv('quizzes.csv')
    for q in quizzes:
        q['id'] = uuid.UUID(q['id'])
        q['course_id'] = uuid.UUID(q['course_id'])
        q['teacher_id'] = uuid.UUID(q['teacher_id'])

    op.bulk_insert(
        sa.table('quizzes',
            sa.column('id', sa.UUID),
            sa.column('course_id', sa.UUID),
            sa.column('teacher_id', sa.UUID),
            sa.column('title', sa.String),
            sa.column('description', sa.String),
            sa.column('created_at', sa.DateTime)
        ),
        quizzes
    )

    # 8. QUIZ QUESTIONS
    questions = read_csv('quiz_questions.csv')
    for q in questions:
        q['id'] = uuid.UUID(q['id'])
        q['quiz_id'] = uuid.UUID(q['quiz_id'])
        q['points'] = int(q['points'])
        q['timer'] = int(q['timer'])
        q['order_index'] = int(q['order_index'])

    op.bulk_insert(
        sa.table('quiz_questions',
            sa.column('id', sa.UUID),
            sa.column('quiz_id', sa.UUID),
            sa.column('text', sa.String),
            sa.column('type', sa.String),
            sa.column('points', sa.Integer),
            sa.column('timer', sa.Integer),
            sa.column('order_index', sa.Integer),
            sa.column('extra_data', sa.JSON)
        ),
        questions
    )

    # 9. QUIZ ANSWERS
    answers = read_csv('quiz_answers.csv')
    for a in answers:
        a['id'] = uuid.UUID(a['id'])
        a['question_id'] = uuid.UUID(a['question_id'])
        a['is_correct'] = a['is_correct'].lower() == 'true'

    op.bulk_insert(
        sa.table('quiz_answers',
            sa.column('id', sa.UUID),
            sa.column('question_id', sa.UUID),
            sa.column('text', sa.String),
            sa.column('is_correct', sa.Boolean)
        ),
        answers
    )

    # 10. SESSION QUIZZES
    session_quizzes = read_csv('session_quizzes.csv')
    for sq in session_quizzes:
        sq['id'] = uuid.UUID(sq['id'])
        sq['session_id'] = uuid.UUID(sq['session_id'])
        sq['quiz_id'] = uuid.UUID(sq['quiz_id'])

    op.bulk_insert(
        sa.table('session_quizzes',
            sa.column('id', sa.UUID),
            sa.column('session_id', sa.UUID),
            sa.column('quiz_id', sa.UUID),
            sa.column('launched_at', sa.DateTime),
            sa.column('ended_at', sa.DateTime)
        ),
        session_quizzes
    )

    # 11. QUIZ SUBMISSIONS
    submissions = read_csv('quiz_submissions.csv')
    for s in submissions:
        s['id'] = uuid.UUID(s['id'])
        s['session_quiz_id'] = uuid.UUID(s['session_quiz_id'])
        s['student_id'] = uuid.UUID(s['student_id'])
        s['score'] = int(s['score'])

    op.bulk_insert(
        sa.table('quiz_submissions',
            sa.column('id', sa.UUID),
            sa.column('session_quiz_id', sa.UUID),
            sa.column('student_id', sa.UUID),
            sa.column('answers', sa.JSON),
            sa.column('score', sa.Integer),
            sa.column('submitted_at', sa.DateTime)
        ),
        submissions
    )

    # 12. REACTIONS
    reactions = read_csv('reactions.csv')
    for r in reactions:
        r['id'] = uuid.UUID(r['id'])
        r['session_id'] = uuid.UUID(r['session_id'])
        r['student_id'] = uuid.UUID(r['student_id'])

    op.bulk_insert(
        sa.table('reactions',
            sa.column('id', sa.UUID),
            sa.column('session_id', sa.UUID),
            sa.column('student_id', sa.UUID),
            sa.column('type', sa.String),
            sa.column('created_at', sa.DateTime)
        ),
        reactions
    )

    # 13. ANNOUNCEMENTS
    announcements = read_csv('announcements.csv')
    for a in announcements:
        a['id'] = uuid.UUID(a['id'])
        a['teacher_id'] = uuid.UUID(a['teacher_id'])
        a['course_id'] = uuid.UUID(a['course_id']) if a['course_id'] else None

    op.bulk_insert(
        sa.table('announcements',
            sa.column('id', sa.UUID),
            sa.column('teacher_id', sa.UUID),
            sa.column('course_id', sa.UUID),
            sa.column('title', sa.String),
            sa.column('content', sa.Text),
            sa.column('type', sa.String),
            sa.column('created_at', sa.DateTime)
        ),
        announcements
    )

    # 14. ACHIEVEMENTS
    achievements = read_csv('achievements.csv')
    for a in achievements:
        a['id'] = uuid.UUID(a['id'])
        a['student_id'] = uuid.UUID(a['student_id'])

    op.bulk_insert(
        sa.table('achievements',
            sa.column('id', sa.UUID),
            sa.column('student_id', sa.UUID),
            sa.column('type', sa.String),
            sa.column('title', sa.String),
            sa.column('description', sa.String),
            sa.column('earned_at', sa.DateTime)
        ),
        achievements
    )


def downgrade() -> None:
    tables = [
        'achievements', 'announcements', 'reactions', 'quiz_submissions',
        'session_quizzes', 'quiz_answers', 'quiz_questions', 'quizzes',
        'session_participants', 'sessions', 'lectures', 'course_enrollments',
        'courses', 'users'
    ]
    for table in tables:
        op.execute(f'DELETE FROM {table}')