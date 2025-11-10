# file: api/routers/transcription.py
import os
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, HTTPException
from .transcription import transcription_service
from .models import TranscriptionResponse

logger = logging.getLogger(__name__)
audio_router = APIRouter()
TEMP_AUDIO_DIR = "temp_audio"

@audio_router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Транскрибация аудиофайла"
)
async def create_transcription_endpoint(
    voice: Annotated[UploadFile, File(description="Аудиофайл для транскрибации")]
):
    if not voice.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Необходим аудиофайл.")

    file_extension = voice.filename.split('.')[-1] if '.' in voice.filename else 'tmp'
    temp_file_path = os.path.join(TEMP_AUDIO_DIR, f"{uuid.uuid4()}.{file_extension}")

    try:
        with open(temp_file_path, "wb") as f:
            f.write(await voice.read())
        
        transcribed_text = await transcription_service.transcribe(temp_file_path)

        if not transcribed_text:
            raise HTTPException(status_code=422, detail="Не удалось распознать речь в аудио.")
        
        return TranscriptionResponse(text=transcribed_text)
    
    except Exception as e:
        logger.error(f"Ошибка в эндпоинте /transcribe: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
