from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timezone

from vkr_itmo.db.models import Achievement, CourseEnrollment, SessionParticipant, QuizSubmission


ACHIEVEMENT_DEFINITIONS = [
    {
        "type": "first_course",
        "field": "courses",
        "threshold": 1,
        "title": "Студент",
        "description": "Записался на первый курс",
    },
    {
        "type": "courses_3",
        "field": "courses",
        "threshold": 3,
        "title": "Многозадачность",
        "description": "Записался на 3 курса одновременно",
    },
    {
        "type": "first_lecture",
        "field": "lectures",
        "threshold": 1,
        "title": "Первый шаг",
        "description": "Посетил первую лекцию",
    },
    {
        "type": "lectures_5",
        "field": "lectures",
        "threshold": 5,
        "title": "Постоянный гость",
        "description": "Посетил 5 лекций",
    },
    {
        "type": "lectures_10",
        "field": "lectures",
        "threshold": 10,
        "title": "Завсегдатай",
        "description": "Посетил 10 лекций",
    },
    {
        "type": "lectures_25",
        "field": "lectures",
        "threshold": 25,
        "title": "Ветеран",
        "description": "Посетил 25 лекций",
    },
    {
        "type": "first_quiz",
        "field": "quizzes",
        "threshold": 1,
        "title": "Первый квиз",
        "description": "Прошёл первый квиз",
    },
    {
        "type": "quizzes_5",
        "field": "quizzes",
        "threshold": 5,
        "title": "Опытный",
        "description": "Прошёл 5 квизов",
    },
    {
        "type": "quizzes_10",
        "field": "quizzes",
        "threshold": 10,
        "title": "Профессионал",
        "description": "Прошёл 10 квизов",
    },
]


async def check_and_award_achievements(student_id: UUID, db: AsyncSession) -> None:
    already_result = await db.execute(
        select(Achievement.type).where(Achievement.student_id == student_id)
    )
    already_earned = {row[0] for row in already_result.all()}

    courses_count_result = await db.execute(
        select(func.count()).where(CourseEnrollment.student_id == student_id)
    )
    courses_count = courses_count_result.scalar() or 0

    lectures_count_result = await db.execute(
        select(func.count()).where(SessionParticipant.student_id == student_id)
    )
    lectures_count = lectures_count_result.scalar() or 0

    quizzes_count_result = await db.execute(
        select(func.count()).where(QuizSubmission.student_id == student_id)
    )
    quizzes_count = quizzes_count_result.scalar() or 0

    counts = {
        "courses": courses_count,
        "lectures": lectures_count,
        "quizzes": quizzes_count,
    }

    for defn in ACHIEVEMENT_DEFINITIONS:
        if defn["type"] in already_earned:
            continue
        if counts[defn["field"]] >= defn["threshold"]:
            achievement = Achievement(
                student_id=student_id,
                type=defn["type"],
                title=defn["title"],
                description=defn["description"],
                earned_at=datetime.now(timezone.utc),
            )
            db.add(achievement)

    await db.commit()
