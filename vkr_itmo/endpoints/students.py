from fastapi import APIRouter

#
# from mpi_project.auth import CurrentUser
#
api_router = APIRouter(prefix="/students", tags=["students"])
#
# security = HTTPBasic()
#
#
# @api_router.get("/users/me")
# def read_current_user(user: CurrentUser):
#     return {"username": user.name}
