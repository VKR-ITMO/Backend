from fastapi import FastAPI
from uvicorn import run

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
    bind_routes(application)
    return application


app = get_app()

if __name__ == "__main__":
    run(
        "vkr_itmo.__main__:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=True,
        reload_dirs=["vkr_itmo"],
        log_level="debug",
    )
