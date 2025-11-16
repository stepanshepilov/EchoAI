import asyncio
import logging
import whisper

logger = logging.getLogger(__name__)

MODEL_NAME = "base"
logger.info(f"Загружаю модель Whisper: {MODEL_NAME}...")

try:
    _whisper_model = whisper.load_model(MODEL_NAME, device="cpu")
    logger.info("Модель Whisper успешно загружена.")

except Exception as e:
    logger.critical(f"Не удалось загрузить модель Whisper: {e}", exc_info=True)
    _whisper_model = None


async def transcribe_audio(file_path: str) -> dict:
    if not _whisper_model:
        return {"error": "Модель Whisper не загружена."}

    logger.info(f"Начинаю транскрибацию файла: {file_path}")
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _whisper_model.transcribe(
                file_path,
                language="ru",
                fp16=False,
                task="transcribe"
            )
        )

        transcribed_text = result.get("text", "").strip()
        logger.info(f"Транскрибация завершена. Длина текста: {len(transcribed_text)} символов.")

        if not transcribed_text:
            logger.warning(f"Речь в файле {file_path} не распознана.")
            return {"error": "Не удалось распознать речь."}

        return {"text": transcribed_text}

    except Exception as e:
        logger.error(f"Ошибка при транскрибации файла {file_path}: {e}", exc_info=True)
        return {"error": f"Внутренняя ошибка сервиса транскрибации."}
