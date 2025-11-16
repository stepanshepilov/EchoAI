import logging
from typing import Dict, Any
from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.ai_services.analyzer.nlp_analyzer import nlp_service
from src.ai_services.prompts.questions import QUESTIONS

logger = logging.getLogger(__name__)


async def analyze_user_session(telegram_id: int) -> Dict[str, Any]:
    logger.info(f"Запуск анализа последней сессии для telegram_id: {telegram_id}")

    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)

        employee = await repo.get_employee(telegram_id=telegram_id)
        if not employee:
            logger.warning(f"Попытка анализа для несуществующего пользователя: {telegram_id}")
            return {"error": f"Пользователь с telegram_id {telegram_id} не найден."}

        last_session = await repo.get_last_session_for_employee(employee_id=employee.id)
        if not last_session:
            logger.warning(f"У пользователя {telegram_id} нет сессий для анализа.")
            return {"error": "Не найдено сессий для анализа."}

        session_id = last_session.id
        logger.info(f"Найдена последняя сессия для анализа: {session_id}")

        full_dialogue_text = ""
        messages = await repo.get_conversation_history(session_id=session_id)

        if messages:
            messages_to_process = messages[-20:]
            full_dialogue_text = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in messages_to_process
            )
        else:
            logger.warning(f"Сессия {session_id} не содержит сообщений.")

        last_survey = await repo.get_survey_result(employee_id=employee.id)
        if last_survey:
            survey_details = ["\n\nРезультаты последнего опроса:"]
            for q_num_str, q_text in QUESTIONS.items():
                answer = last_survey.get(f"q{q_num_str}")
                if answer is not None:
                    survey_details.append(f"- {q_text}: {answer}")
            if len(survey_details) > 1:
                full_dialogue_text += "\n".join(survey_details)
        else:
            logger.warning(f"Результаты опроса для пользователя {employee.id} не найдены.")

        if not full_dialogue_text.strip():
            logger.error(f"Анализ невозможен: нет ни сообщений, ни результатов опроса для сессии {session_id}.")
            return {"error": "Нет данных для анализа."}

        try:
            logger.info(f"Отправка текста на анализ сентимента...")
            sentiment_result = await nlp_service.analyze_sentiment(full_dialogue_text)
            if "error" in sentiment_result:
                raise ValueError(f"Ошибка анализа сентимента: {sentiment_result['error']}")

            logger.info(f"Отправка текста на анализ топиков...")
            topics_result = await nlp_service.analyze_topics(full_dialogue_text)
            if "error" in topics_result:
                raise ValueError(f"Ошибка анализа топиков: {topics_result['error']}")

        except Exception as e:
            logger.exception(f"Ошибка во время NLP-анализа для сессии {session_id}: {e}")
            return {"error": "Ошибка сервиса анализа."}

        analysis_data_to_save = {
            "sentiment": sentiment_result.get("sentiment"),
            "is_burnout_risk_detected": sentiment_result.get("is_burnout_risk_detected"),
            "comment": topics_result.get("comment")
        }

        logger.info(f"Сохранение результата анализа для сессии {session_id}...")
        saved_analysis = await repo.save_analysis(session_id=session_id, analysis_data=analysis_data_to_save)

        logger.info(f"Анализ для сессии {session_id} успешно сохранен.")

        return {
            "session_id": saved_analysis.session_id,
            "sentiment": saved_analysis.sentiment,
            "is_burnout_risk_detected": saved_analysis.is_burnout_risk_detected,
            "comment": saved_analysis.comment
        }


if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--telegram-id", type=int, required=True)
    args = parser.parse_args()
    telegram_id = args.telegram_id
    asyncio.run(analyze_user_session(telegram_id))
