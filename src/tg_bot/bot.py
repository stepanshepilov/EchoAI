import os
import uuid
import asyncio
from pathlib import Path
from typing import Callable, Dict, Any, Awaitable
import time
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

from src.ai_services.whisper_service.speech_to_text import transcribe_audio
from src.ai_services.base import ChatLM
from src.settings import settings
from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.tg_bot.ws_service import ws_notifier 
from src.ai_services.analyzer.analyzer_service import analyze_user_session
from src.ai_services.prompts.questions import QUESTIONS, ANSWER_OPTIONS
from src.ai_services.analyzer.test_analyzer import get_ai_recommended_questions
from src.ai_services.analyzer.give_recommends import send_session_feedback

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
            logger.info(f"Для нового пользователя {telegram_id} стартовала сессия {new_db_session.id}")
            await ws_notifier.send({
                "user_id": telegram_id,
                "event": "session_started",
                "session_id": new_db_session.id
            })

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


# === Общие обработчики ===
# /start
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Единственный обработчик /start, который решает, что делать с пользователем."""
    
    if await state.get_state() is not None:        
        logger.info(f'Пользователь {message.from_user.id} вышел из системы')
        analyze_result = await analyze_user_session(message.from_user.id)
        print(analyze_result)

    await state.clear() 

    user = await get_db_user(message.from_user.id, message.from_user.full_name, state)
    
    if user:
        # Пользователь уже есть в БД
        logger.info(f"Вход для существующего пользователя {user['user_id']}")
        await message.answer(f"С возвращением, {user['name']}! Готовим для вас небольшой опрос 📝")
        is_new_user = False
    else:
        # Новый пользователь
        logger.info(f"Новый пользователь {message.from_user.id}, запуск регистрации.")
        await create_db_user(message.from_user.id, message.from_user.full_name, state)
        await message.answer(f"Добро пожаловать, {message.from_user.full_name}!")
        is_new_user = True

    await start_survey(message, state, is_new_user=is_new_user)


# /finish
@dp.message(Command("finish"))
async def logout(message: Message, state: FSMContext):
    if await state.get_state() is not None:
        logger.info(f'Пользователь {message.from_user.id} вышел из системы')
        await message.answer("Сессия завершена. Нажмите /start, чтобы начать новую", reply_markup=ReplyKeyboardRemove())
        
        await send_session_feedback(telegram_id=message.from_user.id,bot=bot)
        
        await analyze_user_session(message.from_user.id)
        await state.clear()
    else:
        logger.warning(f'Пользователь {message.from_user.id} пытался завершить несуществующую сессию.')
        await message.answer("Нажмите /start, чтобы начать сессию.")
    
    
@dp.message(Command("dialogue"))
async def start_dialogue(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    # Проверяем, не находится ли пользователь уже в диалоге
    if current_state == UserStates.authenticated:
        await message.answer("Я уже слушаю вас. Просто напишите или отправьте голосовое сообщение.")
        return

    user = await get_db_user(message.from_user.id, message.from_user.full_name, state)
      
    if not user: 
        user = await create_db_user(message.from_user.id, message.from_user.full_name, state)
    # Проверяем, прошел ли пользователь регистрацию/опрос
    # (предполагаем, что session_id есть в FSM только у аутентифицированных)
    # user_data = await state.get_data()
    # if not user_data.get(FSM_SESSION_ID_KEY):
    #     await message.answer("Пожалуйста, сначала пройдите первичную настройку с помощью команды /start.")
    #     return

    # Если все проверки пройдены, переключаем состояние и приглашаем к диалогу
    await state.set_state(UserStates.authenticated)
    logger.info(f"Пользователь {message.from_user.id} начал диалог с помощью команды /dialogue.")
    await message.answer("Рад начать наш разговор. Что у вас на уме?")


# Перехватываем все сообщения без состояния
@dp.message(StateFilter(None))
async def any_message_without_state(message: Message):
    await message.answer("Для начала работы, пожалуйста, введите команду /start")



# ==== ЛОГИКА ОПРОСА ====
async def start_survey(message: Message, state: FSMContext, is_new_user: bool = False):
    """
    Инициирует процесс опроса.
    """
    await state.set_state(UserStates.in_survey)
    
    questions_to_ask = None 
    if not is_new_user:
        result = await get_ai_recommended_questions(telegram_id=message.chat.id)
        
        if 'question_indices' in result:
            indices = result['question_indices']
            questions_to_ask = {key: QUESTIONS[key] for key in indices if key in QUESTIONS}

    if is_new_user or not questions_to_ask: 
        logger.info(f"Запуск стандартного опроса для пользователя {message.chat.id}")
        questions_to_ask = {key: QUESTIONS[key] for key in [1, 8, 9, 10, 12]}

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
    russian_answer = ANSWER_OPTIONS.get(user_answer, user_answer)
    answers[question_number] = russian_answer
    
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
        await callback.message.answer(
            "Спасибо за ваши ответы! Опрос завершен.\n"
            "Расскажите как прошел ваш рабочий день?"
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
                print(answers)

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
        # await ws_notifier.send({
        #     "user_id": telegram_id,
        #     "event": "new_message",
        #     "session_id": session_id,
        #     "message": {
        #         "role": user_message_obj.role,
        #         "content": user_message_obj.content,
        #         "timestamp": user_message_obj.timestamp.isoformat()
        #     }
        # })

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



 # /dialogue
# async def start_dialoge_with_ai():


# === Ежедневнная рассылка ===
async def send_daily_initiation(bot: Bot):
    """
    Функция, которая будет запускаться по расписанию.
    Она получает всех пользователей из БД и отправляет им сообщение.
    """
    logger.info("Запуск ежедневной рассылки...")
    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        user_ids = await repo.get_all_active_users()

    if not user_ids:
        logger.info("В базе данных нет пользователей для рассылки.")
        return

    # Текст можно сделать более привлекательным
    message_text = (
        "👋 Привет! Время для нашего ежедневного чекапа.\n\n"
        "Как вы себя чувствуете сегодня? Давайте пройдем короткий опрос, чтобы это выяснить. "
        "Нажмите /start, чтобы начать."
    )
    
    # Счётчики для статистики
    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message_text)
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
            sent_count += 1
        except Exception as e:
            # Эта обработка важна: если один юзер заблокировал бота,
            # рассылка для остальных не должна останавливаться.
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed_count += 1
        await asyncio.sleep(0.1) # Небольшая задержка, чтобы не перегружать API Telegram

    logger.info(f"Рассылка завершена. Отправлено: {sent_count}, Ошибок: {failed_count}")


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
        ),
        BotCommand(
            command="/dialogue",
            description="Начать диалог с Echo 🗨"
        )
    ]
    await bot.set_my_commands(main_menu_commands)

async def main():
    dp.message.middleware(SessionTimeoutMiddleware())

    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)


        # Устанавливаем часовой пояс Москвы
    moscow_tz = pytz.timezone('Europe/Moscow')
    scheduler = AsyncIOScheduler(timezone=moscow_tz)

    # Добавляем задачу: вызывать send_daily_initiation каждый день в 13:00
    scheduler.add_job(
        send_daily_initiation,
        trigger='cron',
        hour=19,
        minute=55,
        kwargs={'bot': bot}  # Передаем объект bot в нашу функцию
    )
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("Планировщик задач запущен.")

    await dp.start_polling(bot)
    


if __name__ == "__main__":
    asyncio.run(main())