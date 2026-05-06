from .students import api_router as students_router
from .auth import api_router as auth_router
from .users import api_router as users_router
from .courses import api_router as courses_router
from .lectures import api_router as lectures_router
from .sessions import api_router as sessions_router
from .websocket import api_router as websocket_router
from .quizzes import api_router as quizzes_router
from .quizzes import runtime_router
from .quizzes import submissions_router
from .reactions import api_router as reactions_router
routes = [
    auth_router,
    students_router,
    users_router,
    courses_router,
    lectures_router,
    sessions_router,
    websocket_router,
    quizzes_router,
    runtime_router,
    submissions_router,
    reactions_router,
]


__all__ = [
    "routes",
]
