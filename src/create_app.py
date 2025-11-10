import os
import logging
from fastapi import FastAPI, APIRouter
from .core.log import setup_logging
from .settings import settings
from .api.v1.views import audio_router

setup_logging()
logger = logging.getLogger(__name__)

os.makedirs("temp_audio", exist_ok=True)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json"
    )

    api_router = APIRouter(prefix=settings.API_V1_STR)
    api_router.include_router(audio_router, tags=["Transcription"])

    app.include_router(api_router)
    
    return app
