from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Enum,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum
import uuid

DeclarativeBase = declarative_base()


# Enums
class UserRole(enum.Enum):
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"



class CourseStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class LectureStatus(enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class QuizQuestionType(enum.Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    BOOLEAN = "BOOLEAN"
    FILE = "FILE"
    TEXT = "TEXT"
    ORDERING = "ORDERING"
    MATCHING = "MATCHING"


class AnnouncementType(enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"


class ReactionType(enum.Enum):
    THUMBS_UP = "THUMBS_UP"
    HEART = "HEART"
    CLAP = "CLAP"
    THINKING = "THINKING"
    CONFUSED = "CONFUSED"
    FIRE = "FIRE"


# Models
class User(DeclarativeBase):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    taught_courses = relationship(
        "Course", back_populates="teacher", foreign_keys="Course.teacher_id"
    )
    enrollments = relationship(
        "CourseEnrollment",
        back_populates="student",
        foreign_keys="CourseEnrollment.student_id",
    )
    lectures = relationship(
        "Lecture", back_populates="teacher", foreign_keys="Lecture.teacher_id"
    )
    sessions = relationship(
        "Session", back_populates="teacher", foreign_keys="Session.teacher_id"
    )
    session_participations = relationship(
        "SessionParticipant",
        back_populates="student",
        foreign_keys="SessionParticipant.student_id",
    )
    quizzes = relationship(
        "Quiz", back_populates="teacher", foreign_keys="Quiz.teacher_id"
    )
    reactions = relationship(
        "Reaction", back_populates="student", foreign_keys="Reaction.student_id"
    )
    announcements = relationship(
        "Announcement", back_populates="teacher", foreign_keys="Announcement.teacher_id"
    )
    achievements = relationship(
        "Achievement", back_populates="student", foreign_keys="Achievement.student_id"
    )


class Course(DeclarativeBase):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    semester = Column(String, nullable=False)
    status = Column(Enum(CourseStatus), nullable=False, default=CourseStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    teacher = relationship(
        "User", back_populates="taught_courses", foreign_keys=[teacher_id]
    )
    enrollments = relationship(
        "CourseEnrollment", back_populates="course", cascade="all, delete-orphan"
    )
    lectures = relationship(
        "Lecture", back_populates="course", cascade="all, delete-orphan"
    )
    quizzes = relationship(
        "Quiz", back_populates="course", cascade="all, delete-orphan"
    )
    announcements = relationship(
        "Announcement", back_populates="course", cascade="all, delete-orphan"
    )


class CourseEnrollment(DeclarativeBase):
    __tablename__ = "course_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="enrollments")
    student = relationship("User", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint(
            "course_id", "student_id", name="unique_course_student_enrollment"
        ),
    )


class Lecture(DeclarativeBase):
    __tablename__ = "lectures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    description = Column(String, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(LectureStatus), nullable=False, default=LectureStatus.DRAFT)
    access_code = Column(String(6), unique=True, nullable=True)
    max_participants = Column(Integer, nullable=True)
    enabled_reactions = Column(
        JSON, nullable=False, default=lambda: ["thumbsUp", "heart", "clap"]
    )
    is_free_session = Column(Boolean, nullable=False, default=False)

    # Relationships
    course = relationship("Course", back_populates="lectures")
    teacher = relationship("User", back_populates="lectures", foreign_keys=[teacher_id])
    sessions = relationship(
        "Session", back_populates="lecture", cascade="all, delete-orphan"
    )


class Session(DeclarativeBase):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecture_id = Column(UUID(as_uuid=True), ForeignKey("lectures.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_code = Column(String, unique=True, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    total_participants = Column(Integer, nullable=False, default=0)
    total_reactions = Column(Integer, nullable=False, default=0)
    total_quizzes = Column(Integer, nullable=False, default=0)

    # Relationships
    lecture = relationship("Lecture", back_populates="sessions")
    teacher = relationship("User", back_populates="sessions", foreign_keys=[teacher_id])
    participants = relationship(
        "SessionParticipant", back_populates="session", cascade="all, delete-orphan"
    )
    session_quizzes = relationship(
        "SessionQuiz", back_populates="session", cascade="all, delete-orphan"
    )
    reactions = relationship(
        "Reaction", back_populates="session", cascade="all, delete-orphan"
    )


class SessionParticipant(DeclarativeBase):
    __tablename__ = "session_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("Session", back_populates="participants")
    student = relationship("User", back_populates="session_participations")

    __table_args__ = (
        UniqueConstraint(
            "session_id", "student_id", name="unique_session_student_participant"
        ),
    )


class Quiz(DeclarativeBase):
    __tablename__ = "quizzes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    course = relationship("Course", back_populates="quizzes")
    teacher = relationship("User", back_populates="quizzes", foreign_keys=[teacher_id])
    questions = relationship(
        "QuizQuestion", back_populates="quiz", cascade="all, delete-orphan"
    )
    session_quizzes = relationship(
        "SessionQuiz", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(DeclarativeBase):
    __tablename__ = "quiz_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False)
    text = Column(String, nullable=False)
    type = Column(Enum(QuizQuestionType), nullable=False)
    points = Column(Integer, nullable=False, default=1)
    timer = Column(Integer, nullable=False)  # seconds
    order_index = Column(Integer, nullable=False)
    extra_data = Column(JSON, nullable=True)

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")
    answers = relationship(
        "QuizAnswer", back_populates="question", cascade="all, delete-orphan"
    )


class QuizAnswer(DeclarativeBase):
    __tablename__ = "quiz_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True), ForeignKey("quiz_questions.id"), nullable=False
    )
    text = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    # Relationships
    question = relationship("QuizQuestion", back_populates="answers")


class SessionQuiz(DeclarativeBase):
    __tablename__ = "session_quizzes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    quiz_id = Column(UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=False)
    launched_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("Session", back_populates="session_quizzes")
    quiz = relationship("Quiz", back_populates="session_quizzes")
    submissions = relationship(
        "QuizSubmission", back_populates="session_quiz", cascade="all, delete-orphan"
    )


class QuizSubmission(DeclarativeBase):
    __tablename__ = "quiz_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_quiz_id = Column(
        UUID(as_uuid=True), ForeignKey("session_quizzes.id"), nullable=False
    )
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    answers = Column(JSON, nullable=False)  # {questionId: answerId[]}
    score = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session_quiz = relationship("SessionQuiz", back_populates="submissions")
    student = relationship("User")


class Reaction(DeclarativeBase):
    __tablename__ = "reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(ReactionType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="reactions")
    student = relationship("User", back_populates="reactions")


class Announcement(DeclarativeBase):
    __tablename__ = "announcements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    type = Column(Enum(AnnouncementType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    teacher = relationship(
        "User", back_populates="announcements", foreign_keys=[teacher_id]
    )
    course = relationship("Course", back_populates="announcements")


class Achievement(DeclarativeBase):
    __tablename__ = "achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)  # e.g., first_quiz, streak_7
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("User", back_populates="achievements")
