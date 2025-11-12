import os
import uuid
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.ai_services.whisper_service.speech_to_text import transcribe_audio
from src.ai_services.base import ChatLM
AI = ChatLM()
FSM_CONTEXT_HISTORY_KEY = 'conversation_history'

# ==== ЗАГЛУШКИ ДЛЯ РАБОТЫ С БАЗАМИ ДАННЫХ ====

async def find_user_in_local_db(user_id: int):
    """Ищет пользователя в нашей основной БД. Возвращает dict или None."""
    logger.info(f"[DB Stub] Поиск пользователя {user_id} в локальной БД...")
    # Имитация: предположим, что пользователя 12345 нет, а 54321 есть
    if user_id == 1231423505: 
        return {"user_id": 1231423505, "name": "Kate Semenova", "cdek_id": "CDEK-777"}
    return None 

async def find_user_by_cdek_id(cdek_id: str):
    """Ищет пользователя во внешней БД (СДЭК). Возвращает dict или None."""
    logger.info(f"[DB Stub] Поиск CDEK ID {cdek_id} во внешней БД...")
    # Имитация:
    if cdek_id == "123":
        return {"name": "Стёпа", "phone": "11117", "city": "Томск"}
    return None

async def create_local_user_simple(user_id: int, full_name: str):
    """Создает простого пользователя в нашей БД."""
    logger.info(f"[DB Stub] Создание простого пользователя: {user_id}, {full_name}")
    # Заглушка
    return {"user_id": user_id, "name": full_name, "cdek_id": None}

async def create_local_user_from_cdek(user_id: int, cdek_id: str, cdek_data: dict):
    """Создает пользователя в нашей БД на основе данных из СДЭК."""
    logger.info(f"[DB Stub] Создание пользователя {user_id} из данных СДЭК {cdek_id}")
    # Заглушка
    return {"user_id": user_id, "name": cdek_data["name"], "cdek_id": cdek_id}


# ==== Настройки ====
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_DIR = Path(__file__).resolve().parent
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ==== Инициализация ====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# === Клавиатуры ===
def get_cdek_question_keyboard() -> InlineKeyboardMarkup:
    """Возвращает инлайн-клавиатуру с вопросом про CDEK ID."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="cdek_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="cdek_no")]
    ])


# === Состояния ===
class UserStates(StatesGroup):
    waiting_for_cdek_id = State() # Процесс регистрации
    authenticated = State() # Пользователь зарегестрирован


# ==== Приветствия ====
async def show_authenticated_menu(message: Message, user_name: str):
    await message.answer(
        f"Добро пожаловать, {user_name}!\n\nВы можете написать как прошёл ваш день или записать голосовое сообщение.",
    )

async def ask_about_cdek_id(message: Message):
    await message.answer(
        "Я не нашел вас в своей базе.\n\nЕсть ли у вас CDEK ID?",
        reply_markup=get_cdek_question_keyboard()
    )


# ==== Обработчики (Callback) ====
@dp.callback_query(F.data == "cdek_no")
async def cdek_no_callback_handler(callback: CallbackQuery, state: FSMContext):
    await create_local_user_simple(callback.from_user.id, callback.from_user.full_name)
    await state.set_state(UserStates.authenticated)
    
    # Убираем инлайн-кнопки
    await callback.message.edit_text("Отлично! Вы зарегистрированы.")
    await show_authenticated_menu(callback.message, callback.from_user.full_name)
    await callback.answer()

@dp.callback_query(F.data == "cdek_yes")
async def cdek_yes_callback_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_for_cdek_id)
    await callback.message.edit_text("Пожалуйста, введите ваш CDEK ID:")
    await callback.answer()


# ==== Обработка ввода CDEK ID ====
@dp.message(UserStates.waiting_for_cdek_id, F.text)
async def process_cdek_id_handler(message: Message, state: FSMContext):
    cdek_id_input = message.text
    cdek_data = await find_user_by_cdek_id(cdek_id_input)
    
    if cdek_data:
        # CDEK ID найден во внешней базе
        await create_local_user_from_cdek(message.from_user.id, cdek_id_input, cdek_data)
        await state.set_state(UserStates.authenticated)
        await message.answer("Отлично, я нашел вас!")
        await show_authenticated_menu(message, cdek_data["name"])
    else:
        await message.answer("К сожалению, я не нашел такой CDEK ID. Попробуйте еще раз или нажмите /start, чтобы начать заново.")

# ==== Функционал для авторизованных пользователей ====
# @dp.message(UserStates.authenticated, CommandStart())
# async def logout_handler(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer("Вы успешно вышли из системы. Чтобы начать снова, отправьте любое сообщение.", reply_markup=ReplyKeyboardRemove())


@dp.message(UserStates.authenticated, F.text)
async def handle_text_message(message: Message, state: FSMContext):
    # Загружаем текущую историю разговора из FSM
    user_data = await state.get_data()
    conversation_history = user_data.get(FSM_CONTEXT_HISTORY_KEY, [])
    
    # Добавляем новое сообщение пользователя в историю
    conversation_history.append(
        {"role": "user", "content": message.text}
    )
    try:
        ai_response_text = await AI.get_response(
            conversation_history=conversation_history
        )
    except Exception as e:
        logger.error(f"Ошибка при запросе к AI: {e}")
        ai_response_text = "Произошла ошибка при обработке запроса. Попробуйте позже."

    # Добавляем ответ AI в историю
    conversation_history.append(
        {"role": "assistant", "content": ai_response_text}
    )
    
    # Сохраняем обновленную историю обратно в FSM
    await state.update_data(
        **{FSM_CONTEXT_HISTORY_KEY: conversation_history}
    )
    
    # Отправляем ответ пользователю
    await message.answer(ai_response_text)


# Голосовые сообщения (voice)
@dp.message(UserStates.authenticated, F.voice)
async def handle_voice(message: Message, state: FSMContext):
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
async def set_main_menu(bot: Bot):
    main_menu_commands = [BotCommand(command='/start', description='Перезапустить бота')]
    await bot.set_my_commands(main_menu_commands)


@dp.message(CommandStart(), UserStates.authenticated)
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    user = await find_user_in_local_db(message.from_user.id)
    if user:
        await state.set_state(UserStates.authenticated)
        await show_authenticated_menu(message, user["name"])
    else:
        await ask_about_cdek_id(message)


# Ловит /start и ЛЮБОЕ другое сообщение от пользователя без состояния
@dp.message(StateFilter(None))
async def entry_point_handler(message: Message, state: FSMContext):
    # Сначала проверяем, не является ли это командой /start, которая требует особого поведения
    if message.text == '/start':
        await state.clear() # Полный сброс сессии и истории
    
    user = await find_user_in_local_db(message.from_user.id)
    
    if user:
        # Пользователь найден (уже зарегистрирован)
        logger.info(f"Вход для пользователя {user['user_id']}")
        await state.set_state(UserStates.authenticated)
        
        # Если это было /start, показываем приветствие
        if message.text == '/start':
            await show_authenticated_menu(message, user["name"])
        elif message.voice:
            await handle_voice(message, state)
        elif message.text:
            await handle_text_message(message, state)
            
    else:
        # Пользователь не найден, запускаем регистрацию
        logger.info(f"Новый пользователь {message.from_user.id}, запуск регистрации.")
        await ask_about_cdek_id(message)


async def main():
    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())