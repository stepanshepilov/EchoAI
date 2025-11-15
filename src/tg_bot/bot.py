import os
import uuid
import asyncio
from pathlib import Path
from typing import Callable, Dict, Any, Awaitable
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart, StateFilter, Command
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

#from src.ai_services.whisper_service.speech_to_text import transcribe_audio
from src.ai_services.base import ChatLM
from src.settings import settings
from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.tg_bot.ws_service import ws_notifier
from src.ai_services.analyzer.analyzer_service import analyze_user_session
from src.ai_services.prompts.questions import QUESTIONS, ANSWER_OPTIONS

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

# === Константы === 
FSM_SURVEY_ANSWERS_KEY = 'survey_answers'
FSM_SURVEY_QUESTION_ORDER_KEY = 'survey_question_order'
FSM_SURVEY_CURRENT_INDEX_KEY = 'survey_current_index'
FSM_SURVEY_QUESTIONS_KEY = 'survey_questions'


async def get_QUESTIONS(telegram_id: int) -> dict:
    """
    Имитирует запрос к внешней системе для получения персонализированного
    набора вопросов для существующего пользователя.
    Возвращает словарь формата {номер_вопроса: текст_вопроса}.
    """
    logger.info(f"Получение персонализированных вопросов для 'старого' пользователя {telegram_id}...")
    # В реальной жизни здесь будет http-запрос к вашему API.
    # Сейчас для примера вернем другой набор вопросов.
    await asyncio.sleep(0.5) # Имитация сетевой задержки
    return {
        2: "Чувство усталости или упадка сил в течение дня?",
        5: "Ощущение негативизма или цинизма, связанное с работой?",
        13: "Трудности с концентрацией внимания на рабочих задачах?",
    }


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



# === Клавиатуры ===
# def get_cdek_question_keyboard() -> InlineKeyboardMarkup:
#     """Возвращает инлайн-клавиатуру с вопросом про CDEK ID."""
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="✅ Да", callback_data="cdek_yes")],
#         [InlineKeyboardButton(text="❌ Нет", callback_data="cdek_no")]
#     ])


# === Состояния ===
class UserStates(StatesGroup):
    waiting_for_cdek_id = State() # Процесс ожидани CDEK ID
    authenticated = State() # Пользователь зарегестрирован
    in_survey = State() # Пользовать проходит опрос


# ==== Приветствия ====
async def show_authenticated_menu(message: Message, user_name: str, state: State):
    await message.answer(
        f"Добро пожаловать, {user_name}!",
    )
    await start_survey(message, state, is_new_user=False)


# /start
@dp.message(CommandStart(), StateFilter('*'))
@dp.message(StateFilter(None))
async def restart(message: Message, state: FSMContext):
    await state.clear()
    if await state.get_state() is not None:        
        logger.info(f'Пользователь {message.from_user.id} вышел из системы')
        await analyze_user_session(message.from_user.id)
    await entry_point_handler(message, state)


# /finish
@dp.message(Command("finish"), StateFilter('*'))
@dp.message(StateFilter(None))
async def logout(message: Message, state: FSMContext):
    await state.clear()
    if await state.get_state() is not None:
        logger.info(f'Пользователь {message.from_user.id} вышел из системы')
        await message.answer("Сессия завершена. Нажмите /start, чтобы начать новую", reply_markup=ReplyKeyboardRemove())
        await analyze_user_session(message.from_user.id)
    else: await message.answer("Нажмите /start, чтобы начать сессию.")


# ==== ЛОГИКА ОПРОСА ====
async def start_survey(message: Message, state: FSMContext, is_new_user: bool = False):
    """
    Инициирует процесс опроса.
    """
    await state.set_state(UserStates.in_survey)
    
    # --- Определяем, какой набор вопросов использовать ---
    if is_new_user:
        logger.info(f"Запуск стандартного опроса для нового пользователя {message.chat.id}")
        questions_to_ask = QUESTIONS # Берем стандартный набор из файла
    else:
        # Для старого пользователя получаем персонализированный набор
        questions_to_ask = await get_QUESTIONS(telegram_id=message.chat.id)

    if not questions_to_ask:
        logger.warning(f"Для пользователя {message.chat.id} не найдено вопросов для опроса. Завершение.")
        await state.set_state(UserStates.authenticated)
        await message.answer("На данный момент для вас нет доступных опросов. Попробуйте позже.")
        return

    question_order = list(questions_to_ask.keys())
    
    # Сохраняем в FSM всё необходимое, включая сам словарь с вопросами
    await state.update_data({
        FSM_SURVEY_QUESTIONS_KEY: questions_to_ask, # <-- СОХРАНЯЕМ ВОПРОСЫ
        FSM_SURVEY_ANSWERS_KEY: {},
        FSM_SURVEY_QUESTION_ORDER_KEY: question_order,
        FSM_SURVEY_CURRENT_INDEX_KEY: 0
    })
    
    await message.answer(
        text='Ответьте, пожалуйста, как часто Вы испытываете чувства, перечисленные ниже:',
        reply_markup=ReplyKeyboardRemove()
    )
    
    await send_question(message, state)


# ### ИЗМЕНЕНО: send_question теперь берет вопросы из FSM ###
async def send_question(message: Message, state: FSMContext):
    """
    Формирует и отправляет текущий вопрос опроса.
    """
    user_data = await state.get_data()
    questions_data = user_data.get(FSM_SURVEY_QUESTIONS_KEY, {}) # <-- ПОЛУЧАЕМ ВОПРОСЫ ИЗ FSM
    q_order = user_data.get(FSM_SURVEY_QUESTION_ORDER_KEY, [])
    q_index = user_data.get(FSM_SURVEY_CURRENT_INDEX_KEY, 0)
    
    if q_index >= len(q_order): return

    question_number = q_order[q_index]
    # Берем текст вопроса из словаря, который сохранили в FSM
    question_text = questions_data.get(question_number, "Текст вопроса не найден.")
    
    buttons = [InlineKeyboardButton(text=text, callback_data=f"survey_{key}") for key, text in ANSWER_OPTIONS.items()]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons[i:i+2] for i in range(0, len(buttons), 2)])
    
    await message.answer(
        f"Вопрос {q_index + 1}/{len(q_order)}:\n\n**{question_text}**",
        reply_markup=keyboard, parse_mode="Markdown"
    )

@dp.callback_query(UserStates.in_survey, F.data.startswith("survey_"))
async def survey_answer_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает нажатие на кнопку с ответом.
    """
    await callback.answer() # Убираем "часики" с кнопки
    
    # 1. Извлекаем ответ пользователя из данных кнопки (например, "often")
    user_answer = callback.data.split("_")[1]
    
    # 2. Получаем "карточку опроса"
    user_data = await state.get_data()
    answers = user_data[FSM_SURVEY_ANSWERS_KEY]
    q_order = user_data[FSM_SURVEY_QUESTION_ORDER_KEY]
    q_index = user_data[FSM_SURVEY_CURRENT_INDEX_KEY]
    question_number = q_order[q_index]
    
    # 3. Записываем ответ в словарь
    answers[question_number] = user_answer
    
    # 4. Передвигаем указатель на следующий вопрос
    next_index = q_index + 1
    await state.update_data({
        FSM_SURVEY_ANSWERS_KEY: answers,
        FSM_SURVEY_CURRENT_INDEX_KEY: next_index
    })
    
    # 5. Удаляем предыдущее сообщение с вопросом, чтобы чат был чистым
    await callback.message.delete()
    
    # 6. Проверяем, закончился ли опрос
    if next_index < len(q_order):
        # Если нет - отправляем следующий вопрос
        await send_question(callback.message, state)
    else:
        # Если да - завершаем опрос
        logger.info(f"Пользователь {callback.from_user.id} завершил опрос. Ответы: {answers}")
        await state.set_state(UserStates.authenticated) # Возвращаем в обычное состояние
        # await set_authenticated_commands(bot) # Устанавливаем полное меню команд
        await callback.message.answer(
            "Спасибо за ваши ответы! Опрос завершен.\n"
            "Используйте команду /dialogue, чтобы начать общение."
        )
        try:
            async with AsyncSessionLocal() as db_session:
                repo = SQLiteRepository(db_session)

                # Находим или создаём сотрудника по telegram_id
                employee = await repo.get_or_create_employee(telegram_id=callback.from_user.id)
                normalized_answers = {
                    f"q{int(k)}": v
                    for k, v in answers.items()
                }
                employee_id = employee.id

                await repo.save_survey_result(employee_id=employee_id, answers=normalized_answers)

                logger.info(
                    f"Результаты опроса {answers} для пользователя {callback.from_user.id} "
                    f"(employee_id={employee_id}) сохранены в БД."
                )
        except Exception as e:
            logger.exception(f"Ошибка при сохранении результатов опроса в БД: {e}")


@dp.message(UserStates.in_survey, F.text)
async def wrong_text_in_menu_handler(message: Message):
    """
    Ловит любой текст, который не был пойман предыдущими хэндлерами,
    когда пользователь находится в главном меню (после опроса).
    """
    await message.answer(
        "Пожалуйста, используйте команды из меню или кнопки ниже, чтобы продолжить.",
    )


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
# @dp.message(UserStates.authenticated, F.voice)
# async def handle_voice(message: Message, state: FSMContext):
#     # генерируем имя файла .ogg
#     file_name = f"{uuid.uuid4()}.mp3"
#     dst_path = TEMP_AUDIO_DIR / file_name
#
#     await bot.download(message.voice, destination=dst_path)
#     logger.info(f"Аудиофайл сохранён: {dst_path.as_posix()}")
#
#     result = await transcribe_audio(str(dst_path))
#
#     if "text" in result:
#         await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
#         ai_response_text = await get_ai_answer(result["text"], message.chat.id, state)
#         await message.answer(ai_response_text)
#     else:
#         await message.answer("Не удалось распознать речь 😔")





# Ловит /start и ЛЮБОЕ другое сообщение от пользователя без состояния
@dp.message(StateFilter(None))
@dp.message(~Command("finish"))
async def entry_point_handler(message: Message, state: FSMContext):
    # Сначала проверяем, не является ли это командой /start, которая требует особого поведения
    if message.text == '/start':
        await state.clear() # Полный сброс сессии и истории
    
    user = await get_db_user(message.from_user.id, message.from_user.full_name, state)
    
    if user:
        # Пользователь найден (уже зарегистрирован)
        logger.info(f"Вход для пользователя {user['user_id']}")
        # await state.set_state(UserStates.authenticated)
        # await start_survey(message, state, is_new_user=False)

        
        # Если это было /start, показываем приветствие
        # if message.text == '/start':
        await show_authenticated_menu(message, user["name"], state)
        # elif message.voice:
        #     await handle_voice(message, state)
        # elif message.text:
        #     await handle_text_message(message, state)
            
    else:
        # Пользователь не найден, запускаем регистрацию
        logger.info(f"Новый пользователь {message.from_user.id}, запуск регистрации.")
        await create_db_user(message.from_user.id, message.from_user.full_name, state)
        await message.answer(f"Добро пожаловать, {message.from_user.full_name}!",)
        await start_survey(message, state, is_new_user=True)

        # await ask_about_cdek_id(message)


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
        
	

# ==== Запуск ====
async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(
            command='/start', 
            description='Начать / Перезапустить 🔥'
        ),
        BotCommand(
            command='/finish', 
            description='Завершить сессию 🔚'
        )
    ]
    await bot.set_my_commands(main_menu_commands)

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