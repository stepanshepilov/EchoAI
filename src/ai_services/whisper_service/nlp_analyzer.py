import logging
import os
import openai
from dotenv import load_dotenv
from ..client import get_openai_client

load_dotenv()

logger = logging.getLogger(__name__)

try:
    _llm_client = get_openai_client()
    logger.info("Клиент OpenAI успешно инициализирован.")
except Exception as e:
    logger.critical(f"Не удалось инициализировать клиент OpenAI: {e}")
    _llm_client = None

async def analyze_text_sentiment(text: str) -> dict:
    if not _llm_client:
        return {"error": "Клиент OpenAI не инициализирован."}

    logger.info(f"Отправляю текст на анализ в LLM. Длина: {len(text)}.")
    
    prompt = f"""
    Проанализируй сообщение сотрудника.
    1. Оцени эмоциональный тон по шкале от -1.0 (негативный) до 1.0 (позитивный).
    2. Выдели 1-3 ключевые темы.
    Верни ТОЛЬКО валидный JSON с ключами "sentiment" и "topics".

    Текст для анализа: "{text}"
    """

    try:
        response = await _llm_client.chat.completions.create(
            model="not-needed-here",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.01,
            response_format={"type": "json_object"}
        )

        analytics_data = openai.parse(response)
        sentiment = float(analytics_data.get("sentiment", 0.0))
        topics = analytics_data.get("topics", [])
        logger.info(f"Анализ текста завершен. Сентимент: {sentiment}.")
        
        return {"sentiment": sentiment, "topics": topics}

    except Exception as e:
        logger.error(f"Ошибка при анализе текста LLM: {e}", exc_info=True)
        return {"error": "Внутренняя ошибка сервиса анализа текста."}
