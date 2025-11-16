import asyncio
import logging
import whisper
from ...settings import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    _model = None

    def __init__(self):
        if TranscriptionService._model is None:
            logger.info(f"Загружаю модель Whisper: {settings.WHISPER_MODEL}...")
            try:
                TranscriptionService._model = whisper.load_model(settings.WHISPER_MODEL, device="cpu")
                logger.info("Модель Whisper успешно загружена.")
            except Exception as e:
                logger.critical(f"Не удалось загрузить модель Whisper: {e}", exc_info=True)
                raise RuntimeError("Ошибка инициализации сервиса транскрибации") from e

    async def transcribe(self, file_path: str) -> str:
        logger.info(f"Начинаю транскрибацию файла: {file_path}")
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: self._model.transcribe(file_path, language="ru", fp16=False)
            )
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Ошибка при транскрибации файла {file_path}: {e}", exc_info=True)
            raise


transcription_service = TranscriptionService()
