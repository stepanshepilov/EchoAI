import os
import uuid
import asyncio
from pathlib import Path
from typing import Callable, Dict, Any, Awaitable
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.enums import ChatAction

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.ai_services.whisper_service.speech_to_text import transcribe_audio
from src.ai_services.base import ChatLM
from src.settings import settings
from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.tg_bot.ws_service import ws_notifier 
from src.ai_services.analyzer.analyzer_service import analyze_user_session

# ==== Настройки ====
AI = ChatLM()
FSM_SESSION_ID_KEY = 'current_session_id'

db_file = settings.DATABASE_URL.split('///')[-1]

BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_DIR = Path(__file__).resolve().parent
TEMP_AUDIO_DIR = BASE_DIR / "temp_audio"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TIMEOUT_TASKS: Dict[int, asyncio.Task] = {}
SESSION_TIMEOUT = 500

# ==== Инициализация ====
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==== ДЛЯ РАБОТЫ С БАЗАМИ ДАННЫХ ====
async def begin_new_session(employee_id: int):
    async with AsyncSessionLocal() as session_2:
        repo = SQLiteRepository(session_2)
        new_db_session = await repo.start_new_session(employee_id)
        return new_db_session

async def get_db_user(telegram_id: int, full_name: str, state: FSMContext):
    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        
        employee_object = await repo.get_employee(
            telegram_id=telegram_id
        )
        
        if employee_object:
            new_db_session = await begin_new_session(employee_object.id)
            await state.update_data({FSM_SESSION_ID_KEY: new_db_session.id})
            logger.info(f"Для пользователя {telegram_id} стартовала сессия {new_db_session.id}")

            
            await ws_notifier.send({
                    "user_id": telegram_id,
                    "event": "session_started",
                    "session_id": new_db_session.id
                })

            # Возвращаем словарь для совместимости
            return {
                "user_id": employee_object.telegram_id,
                # Если в модели есть имя - берем его, иначе из Telegram
                "name": employee_object.name or full_name,
            }
    return None


async def create_db_user(telegram_id: int, full_name: str, state: FSMContext, cdek_id: str = None):
    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        employee_object = await repo.create_employee(
            telegram_id=telegram_id,
            name=full_name, 
            cdek_id=cdek_id
            )

        if employee_object:
            new_db_session = await begin_new_session(employee_object.id)
            await state.update_data({FSM_SESSION_ID_KEY: new_db_session.id})
            logger.info(f"Для пользователя {telegram_id} стартовала сессия {new_db_session.id}")

            return {
                "user_id": employee_object.telegram_id,
                "name": getattr(employee_object, 'name', full_name),
            }
    return None


async def start_user_session(telegram_id: int, state: FSMContext):
    """
    Находит пользователя по telegram_id, создает для него новую сессию диалога в БД,
    сохраняет session_id в FSM и возвращает объект Employee.
    Если пользователь не найден, возвращает None.
    """
    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        # 1. Находим пользователя в нашей БД по его telegram_id
        user = await repo.get_employee(telegram_id=telegram_id)
        
        if user:
            # 2. Если нашли, создаем для него новую сессию диалога
            new_db_session = await repo.start_new_session(employee_id=user.id) # <-- Используем user.id (PK)
            
            # 3. Сохраняем ID этой сессии в FSM для дальнейшего использования
            await state.update_data({FSM_SESSION_ID_KEY: new_db_session.id})
            logger.info(f"Для пользователя {telegram_id} (ID: {user.id}) стартовала сессия {new_db_session.id}")
            
            return user
            
    return None


async def find_user_by_cdek_id(cdek_id: str):
    """Ищет пользователя во внешней БД (СДЭК). Возвращает dict или None."""
    logger.info(f"[DB Stub] Поиск CDEK ID {cdek_id} во внешней БД...")
    # Имитация:
    if cdek_id == 123:
        return {}
    return None



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
        f"Добро пожаловать, {user_name}!\n\nКак прошла твоя рабочая неделя? Что было самым запоминающимся?",
    )

async def ask_about_cdek_id(message: Message):
    await message.answer(
        "Я не нашел вас в своей базе.\n\nЕсть ли у вас CDEK ID? \n\nИли нажмите /start",
        reply_markup=get_cdek_question_keyboard()
    )


# /start
@dp.message(~StateFilter(None), CommandStart())
async def restart(message: Message, state: FSMContext):
    await state.clear()
    logger.info(f'Пользователь {message.from_user.id} вышел из системы')
    await message.answer("Вы успешно вышли из сесси. Напишите любое сообщение, чтобы возобновить.", reply_markup=ReplyKeyboardRemove())
    await analyze_user_session(message.from_user.id)
    # await entry_point_handler(message, state)


# ==== Обработчики (Callback) ====
@dp.callback_query(F.data == "cdek_no")
async def cdek_no_callback_handler(callback: CallbackQuery, state: FSMContext):
    await create_db_user(callback.from_user.id, callback.from_user.full_name, state)
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

    if await find_user_by_cdek_id(cdek_id=cdek_id_input):
        await create_db_user(message.from_user.id, message.from_user.full_name, state, cdek_id_input)
        await state.set_state(UserStates.authenticated)
        await message.answer("Отлично, я нашел вас!")
        await show_authenticated_menu(message, message.from_user.full_name)

    else: 
        await message.answer("Такого ID не сущетвует. Попробуйте ещё раз")
    # return 



# ==== Функционал для авторизованных пользователей ====
async def get_ai_answer(message_text, telegram_id: int, state: FSMContext):
    user_data = await state.get_data()
    session_id = user_data.get(FSM_SESSION_ID_KEY)

    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        # Сохраняем сообщение пользователя

        user_message_obj = await repo.add_message(session_id=session_id, role="user", content=message_text)
        await ws_notifier.send({
            "user_id": telegram_id,
            "event": "new_message",
            "session_id": session_id,
            "message": {
                "role": user_message_obj.role,
                "content": user_message_obj.content,
                "timestamp": user_message_obj.timestamp.isoformat()
            }
        })

        # Получаем историю
        history_for_ai = await repo.get_conversation_history(session_id=session_id)
        print('history_for_ai' , history_for_ai)

    try:
        ai_response_text = await AI.get_response(conversation_history=history_for_ai)
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return "Произошла ошибка сессии, пожалуйста, нажмите /start"
        
    async with AsyncSessionLocal() as db_session:
        repo = SQLiteRepository(db_session)
        # Сохраняем ответ AI
        await repo.add_message(session_id=session_id, role="assistant", content=ai_response_text)

    return ai_response_text


# Текстовые сообщения
@dp.message(UserStates.authenticated, F.text)
async def handle_text_message(message: Message, state: FSMContext):

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    ai_response_text = await get_ai_answer(message.text, message.chat.id, state)
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
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        ai_response_text = await get_ai_answer(result["text"], message.chat.id, state)
        await message.answer(ai_response_text)  
    else:
        await message.answer("Не удалось распознать речь 😔")



# ==== Запуск ====
async def set_main_menu(bot: Bot):
    main_menu_commands = [BotCommand(command='/start', description='Перезапустить бота / Главное меню 🔥')]
    # проброс по websoscket строки {'user_id': id, 'event': 'session_started'}
    await bot.set_my_commands(main_menu_commands)



# Ловит /start и ЛЮБОЕ другое сообщение от пользователя без состояния
@dp.message(StateFilter(None))
async def entry_point_handler(message: Message, state: FSMContext):
    # Сначала проверяем, не является ли это командой /start, которая требует особого поведения
    if message.text == '/start':
        await state.clear() # Полный сброс сессии и истории
    
    user = await get_db_user(message.from_user.id, message.from_user.full_name, state)
    
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


#  Функция, которую будет выполнять фоновый тайме
async def _session_timeout(
    user_id: int,
    chat_id: int,
    state: FSMContext,
    bot: Bot
):
    """
    Ожидает заданное время и очищает состояние пользователя, если задача не была отменена.
    """
    try:
        await asyncio.sleep(SESSION_TIMEOUT)
        
        logger.info(f"Сессия для пользователя {user_id} истекла. Очистка состояния.")
        await state.clear()
        
        # Опционально: отправляем сообщение пользователю
        await bot.send_message(
            chat_id,
            "Ваша сессия завершена. "
            "Чтобы продолжить, просто отправьте любое сообщение.",
            reply_markup=ReplyKeyboardRemove()
        )
    except asyncio.CancelledError:
        # Это нормальное поведение, когда мы отменяем задачу при новой активности
        logger.info(f"Таймер сессии для пользователя {user_id} был сброшен.")
    finally:
        # Убираем завершенную или отмененную задачу из словаря
        SESSION_TIMEOUT_TASKS.pop(user_id, None)

# Middleware для управления таймерами сессий 
class SessionTimeoutMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        state: FSMContext = data['state']
        user_id = event.from_user.id

        # 1. Отменяем предыдущий таймер, если он есть
        if user_id in SESSION_TIMEOUT_TASKS:
            SESSION_TIMEOUT_TASKS[user_id].cancel()

        # 2. Создаем и запускаем новый таймер в фоне
        # Передаем bot в data, чтобы он был доступен
        data['bot_instance'] = data['bot']
        session_task = asyncio.create_task(
            _session_timeout(
                user_id=user_id,
                chat_id=event.chat.id,
                state=state,
                bot=data['bot']
            )
        )
        SESSION_TIMEOUT_TASKS[user_id] = session_task
        
        # 3. Передаем управление дальше, чтобы обработать сообщение
        return await handler(event, data)
        


   

async def main():
    dp.message.middleware(SessionTimeoutMiddleware())

    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    # await dp.start_polling(bot)
    
    try:
        await ws_notifier.start()
        await dp.start_polling(bot)
    finally:
        await ws_notifier.stop()
        await bot.session.close() 


if __name__ == "__main__":
    asyncio.run(main())