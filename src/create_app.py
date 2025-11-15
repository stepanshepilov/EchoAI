import os
import logging
from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from .core.log import setup_logging
from .settings import settings
from .db.session import engine
from .db.models import Base
from .api.v1.views import router

setup_logging()
logger = logging.getLogger(__name__)

os.makedirs("temp_audio", exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Поднимаю Backend, инициализирую БД")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("База данных успешно инициализирована.")
    
    yield
    
    logger.info("Приложение останавливается...")
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan
    )

    api_router = APIRouter(prefix=settings.API_V1_STR)
    api_router.include_router(router, tags=["Transcription"])

    app.include_router(api_router)

    origins = [
        "http://localhost:8080",  # <-- ИСПРАВЛЕНО
        "http://localhost",
        "http://127.0.0.1:8080",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app
