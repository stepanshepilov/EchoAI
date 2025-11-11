import os
import uuid
import asyncio
from pathlib import Path
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart

from src.ai_services.whisper_service.speech_to_text import transcribe_audio

logger = logging.getLogger(__name__)

# ==== Настройки ====
# Перед запуском установи переменную окружения BOT_TOKEN или подставь строкой:
BOT_TOKEN = os.getenv("BOT_TOKEN", "8445782769:AAFJjwgIPH4aQmmFEMNz58g8z0NO9MKDkj0")

BASE_DIR = Path(__file__).resolve().parent
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ==== Инициализация ====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Привет!")

# Голосовые сообщения (voice) - Telegram присылает в OGG/Opus
@dp.message(F.voice)
async def handle_voice(message: Message):
    # генерируем имя файла .ogg
    file_name = f"{uuid.uuid4()}.mp3"
    dst_path = TEMP_AUDIO_DIR / file_name

    await bot.download(message.voice, destination=dst_path)
    logger.info(f"Аудиофайл сохранён: {dst_path.as_posix()}")
    
    result = await transcribe_audio(str(dst_path))

    if "text" in result:
        await message.answer(result["text"])
    else:
        await message.answer("Не удалось распознать речь 😔")


# ==== Запуск ====
async def main():
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())