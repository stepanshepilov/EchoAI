import logging
from typing import Dict, Any
from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.ai_services.analyzer.nlp_analyzer import nlp_service
from src.ai_services.prompts.questions import QUESTIONS

logger = logging.getLogger(__name__)

async def analyze_user_session(telegram_id: int) -> Dict[str, Any]:
    """
    Основная функция для анализа последней сессии пользователя.
    1. Находит пользователя по telegram_id.
    2. Находит его последнюю сессию.
    3. Собирает все сообщения из этой сессии.
    4. Отправляет их в NLP-сервис для анализа.
    5. Сохраняет результат анализа в БД.
    """
    logger.info(f"Запуск анализа последней сессии для telegram_id: {telegram_id}")

    # Создаем сессию и репозиторий
    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)

        # 1. Найти пользователя по telegram_id, чтобы получить его внутренний id
        employee = await repo.get_employee(telegram_id=telegram_id)
        if not employee:
            logger.warning(f"Попытка анализа для несуществующего пользователя: {telegram_id}")
            return {"error": f"Пользователь с telegram_id {telegram_id} не найден."}

        # 2. Найти последнюю сессию для этого пользователя
        last_session = await repo.get_last_session_for_employee(employee_id=employee.id)
        if not last_session:
            logger.warning(f"У пользователя {telegram_id} нет ни одной сессии для анализа.")
            return {"error": "Не найдено сессий для анализа."}
        
        session_id = last_session.id
        logger.info(f"Найдена последняя сессия: {session_id}")

        # 3. Взять набор сообщений по session_id
        messages = await repo.get_conversation_history(session_id=session_id)
        messages = messages[-20:]   
        if not messages:
            logger.warning(f"Сессия {session_id} пуста, анализ невозможен.")
            return {"error": "Сессия не содержит сообщений."}
        
        # Объединяем все сообщения в один большой текст для анализа
        full_dialogue_text = "\n".join(
            f"{msg['role']}: {msg['content']}" for msg in messages
        )
        
        last_survey = await repo.get_survey_result(employee_id=employee.id)
        if not last_survey:
            logger.warning(f"Результаты теста для пользоватя {employee.id} не найдены")
            pass 
        else:
            logger.info(f"Найдена тст для: {telegram_id}")
            survey_details = ["\n\nLast survey results:"]
            for q_num, q_text in QUESTIONS.items():
                answer = last_survey.get(f"q{q_num}")
                if answer is not None:
                    survey_details.append(f"- {q_text}: {answer}")

            if len(survey_details) > 1: 
                full_dialogue_text += "\n".join(survey_details)

            else:
                logger.warning(f"Результаты опроса для пользователя {employee.id} не найдены")
            

    print('====================\n', full_dialogue_text)


        
    # 4.1 Передать текст в анализатор
    logger.info(f"Отправка текста сессии {session_id} на анализ в NLP сервис...")
    analysis_result = await nlp_service.analyze_sentiment(full_dialogue_text)
    print('\n\nanalysis_result: ', analysis_result)

    if "error" in analysis_result:
        logger.error(f"Ошибка NLP-анализа для сессии {session_id}: {analysis_result['error']}")
        return analysis_result

    # 4.2 Передать текст в анализатор
    logger.info(f"Отправка текста сессии {session_id} на анализ в NLP топиков...")
    analysis_topics = await nlp_service.analyze_topics(full_dialogue_text)
    print('\n\nanalysis_result: ', analysis_topics)
    if "error" in analysis_topics:
        logger.error(f"Ошибка NLP-анализа для сессии {session_id}: {analysis_topics['error']}")
        return analysis_topics

    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)
        
        # 5. Сохранить результат в dialogue_analysis
        logger.info(f"Сохранение результата анализа для сессии {session_id}...")
        analysis_result['comment'] = analysis_topics['comment']
        saved_analysis = await repo.save_analysis(session_id=session_id, analysis_data=analysis_result)
        
        logger.info(f"Анализ для сессии {session_id} успешно сохранен. Результат: {analysis_result}")
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