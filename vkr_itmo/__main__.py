from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from uvicorn import run
import traceback
import os

from .config import AppConfig
from .endpoints import routes

config = AppConfig()


def bind_routes(fastapi_app: FastAPI):
    for route in routes:
        fastapi_app.include_router(route, prefix=config.PATH_PREFIX)


def get_app() -> FastAPI:
    application = FastAPI(
        title="VKR ITMO",
    )
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("uploads/avatars", exist_ok=True)
    os.makedirs("uploads/course_images", exist_ok=True)
    os.makedirs("uploads/quiz_files", exist_ok=True)
    
    # Mount static files
    application.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://frontend-production-4824.up.railway.app",
            "http://localhost:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
        )
    
    bind_routes(application)
    return application


app = get_app()

# if __name__ == "__main__":
#     run(
#         "vkr_itmo.__main__:app",
#         host=config.APP_HOST,
#         port=config.APP_PORT,
#         reload=True,
#         reload_dirs=["vkr_itmo"],
#         log_level="debug",
#     )
