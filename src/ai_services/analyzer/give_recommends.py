import logging

from aiogram import Bot

from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.ai_services.analyzer.nlp_analyzer import nlp_service
from src.ai_services.prompts.questions import QUESTIONS

logger = logging.getLogger(__name__)


async def send_session_feedback(telegram_id: int, bot: Bot) -> bool:
    logger.info(f"Подготовка и отправка обратной связи для telegram_id: {telegram_id}")
    full_session_text = ""

    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        employee = await repo.get_employee(telegram_id=telegram_id)
        if not employee:
            logger.error(f"Невозможно отправить фидбэк: пользователь {telegram_id} не найден.")
            return False

        last_session = await repo.get_last_session_for_employee(employee_id=employee.id)
        if not last_session:
            logger.warning(f"У пользователя {telegram_id} нет сессий для отправки фидбэка.")
            return False

        messages = await repo.get_conversation_history(session_id=last_session.id)
        if messages:
            full_session_text = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in messages[-20:]
            )

        last_survey = await repo.get_survey_result(employee_id=employee.id)
        if last_survey:
            survey_details = ["\n\nРезультаты последнего опроса:"]
            for q_num_str, q_text in QUESTIONS.items():
                answer = last_survey.get(f"q{q_num_str}")
                if answer is not None:
                    survey_details.append(f"- {q_text}: {answer}")
            if len(survey_details) > 1:
                full_session_text += "\n".join(survey_details)

    if not full_session_text.strip():
        logger.error(f"Невозможно сгенерировать фидбэк: нет данных для пользователя {telegram_id}.")
        return False

    try:
        logger.info(f"Отправка текста сессии для генерации прямого фидбэка...")
        feedback_message = await nlp_service.generate_feedback_from_text(full_session_text)

        if not feedback_message:
            logger.warning(f"Сервис не сгенерировал текст фидбэка для {telegram_id}.")
            return False

        await bot.send_message(
            chat_id=telegram_id,
            text=feedback_message
        )
        logger.info(f"Фидбэк успешно отправлен пользователю {telegram_id}.")
        return True

    except Exception as e:
        logger.exception(f"Не удалось отправить фидбэк пользователю {telegram_id}: {e}")
        return False
