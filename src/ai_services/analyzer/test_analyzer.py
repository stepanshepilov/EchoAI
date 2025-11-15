import logging
from typing import List, Dict, Any
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from src.db.repo import SQLiteRepository
from src.db.session import AsyncSessionLocal
from src.ai_services.prompts.questions import QUESTIONS
from src.ai_services.base import QuestionRecommender


def _parse_indices_from_ai_response(response: str) -> List[int]:
    """
    Безопасно парсит строку от LLM, извлекая из нее числа.
    Пример: " 3, 11, 15 " -> [3, 11, 15]
    """
    if not response:
        return []
    
    indices = [] 
    parts = response.split(',')
    for part in parts:
        try:
            # Убираем лишние пробелы и преобразуем в число
            indices.append(int(part.strip()))
        except (ValueError, TypeError):
            # Игнорируем, если LLM добавила какой-то текст
            logger.warning(f"Не удалось спарсить часть ответа от LLM: '{part}'")
            continue
    return indices


async def get_ai_recommended_questions(telegram_id: int) -> Dict[str, Any]:
    """
    Анализирует предыдущие ответы пользователя с помощью LLM
    и возвращает список индексов для нового, персонального опроса.
    """
    logger.info(f"Запрос на AI-рекомендацию вопросов для telegram_id: {telegram_id}")

    async with AsyncSessionLocal() as session:
        repo = SQLiteRepository(session)

        employee = await repo.get_employee(telegram_id=telegram_id)
        if not employee:
            return {"error": "Пользователь не найден."}

        last_survey = await repo.get_survey_result(employee_id=employee.id)
        if not last_survey:
            # Если предыдущих ответов нет, мы не можем ничего рекомендовать
            return {"error": "Результаты предыдущего опроса не найдены."}

        # 1. Форматируем предыдущие ответы пользователя
        user_answers_list = []
        for q_num, q_text in QUESTIONS.items():
            answer = last_survey.get(f"q{q_num}")
            if answer is not None:
                user_answers_list.append(f"- {q_text}: {answer}")
        
        if not user_answers_list:
            return {"error": "Данные опроса пусты."}

        user_answers_text = "\n".join(user_answers_list)
        
        # 2. Форматируем ВЕСЬ список вопросов для контекста LLM
        all_questions_text = "\n".join(f"{num}: {text}" for num, text in QUESTIONS.items())

        print(f"========================\n{all_questions_text}\n{user_answers_text}")

        # 3. Отправляем в LLM для получения рекомендации
        recommender = QuestionRecommender()
        logger.info("Отправка запроса в LLM для рекомендации вопросов...")
        ai_response = await recommender.recommend(
            all_questions=all_questions_text, 
            user_answers=user_answers_text
        )
        logger.info(f"Получен сырой ответ от LLM: '{ai_response}'")

        # 4. Парсим ответ от LLM
        recommended_indices = _parse_indices_from_ai_response(ai_response)
        
        if not recommended_indices:
            logger.warning("LLM не вернула рекомендации или ответ не удалось спарсить.")
            return {"error": "Не удалось получить рекомендации от AI."}

        logger.info(f"AI рекомендовал вопросы с индексами: {recommended_indices}")
        return {"question_indices": recommended_indices}