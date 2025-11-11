import logging
from typing import Dict, Any
from pydantic import BaseModel, Field, ValidationError
from ..client import get_openai_client 

logger = logging.getLogger(__name__)

class SentimentAnalysisResponse(BaseModel):
    sentiment: float = Field(
        ..., 
        description="Эмоциональный тон по шкале от -1.0 (крайне негативный, выгорание) до 1.0 (позитивный, энергия).",
        ge=-1.0, 
        le=1.0
    )
    topics: list[str] = Field(
        ...,
        description="Список из 1-3 ключевых тем, затронутых в сообщении.",
        max_length=3
    )
    is_burnout_risk: bool = Field(
        ...,
        description="Флаг, указывающий на прямые или косвенные признаки выгорания в тексте (True/False)."
    )

class NlpService:
    def __init__(self):
        self.client = get_openai_client()

        if not self.client:
            raise RuntimeError("Клиент LLM не был инициализирован.")
        
        logger.info("Сервис NLP успешно инициализирован.")

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        logger.info(f"Начинаю анализ текста (длина: {len(text)}).")

        system_prompt = f"""
        Ты — высокоточный AI-аналитик, специализирующийся на психологии труда и выявлении выгорания.
        Твоя задача — проанализировать сообщение сотрудника и извлечь из него структурированную информацию.
        Ты ДОЛЖЕН отвечать ТОЛЬКО в формате JSON, который соответствует предоставленной схеме.

        ### Инструкции по анализу:
        1.  **sentiment**: Оцени эмоциональный фон от -1.0 до 1.0.
            - -1.0: Явные признаки отчаяния, бессилия, агрессии ("всё бесит", "ненавижу работу").
            - -0.5: Усталость, стресс, раздражение ("устал", "закопался", "дедлайн горит").
            -  0.0: Нейтральное или амбивалентное сообщение ("нормально", "работаем").
            - +0.5: Умеренный позитив, удовлетворение ("справился", "интересная задача").
            - +1.0: Явный восторг, энергия ("лучшая неделя", "вдохновляет").

        2.  **topics**: Выдели 1-3 ключевые темы. Будь конкретным.
            - Плохо: "работа". Хорошо: "монотонные отчеты", "конфликт с Ивановым", "успешная презентация".

        3.  **is_burnout_risk**: Поставь `true`, если в тексте есть ХОТЯ БЫ ОДИН из следующих маркеров, иначе `false`:
            - Прямые жалобы на усталость, стресс, потерю смысла.
            - Упоминание потери контроля, цинизма, отстраненности.
            - Сообщения о физическом недомогании, связанном с работой (головные боли, бессонница).
            - Негативная оценка своей профессиональной эффективности ("ничего не успеваю", "я плохой специалист").
        """
        
        user_prompt = f"Проанализируй следующий текст и верни результат в JSON формате:\n\nТекст: \"{text}\""

        try:
            response = await self.client.chat.completions.create(
                model="deepseek-chat", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.01,
                response_format={"type": "json_object"}
            )

            response_content = response.choices[0].message.content
            
            validated_data = SentimentAnalysisResponse.model_validate_json(response_content)
            logger.info(f"Анализ текста завершен. Результат: {validated_data.model_dump()}")
            
            return validated_data.model_dump()

        except ValidationError as e:
            logger.error(f"Ошибка валидации ответа LLM: {e}. Ответ модели: '{response_content}'")
            return {"error": "Некорректный формат ответа от LLM."}
        except Exception as e:
            logger.error(f"Критическая ошибка при анализе текста LLM: {e}", exc_info=True)
            return {"error": "Внутренняя ошибка сервиса NLP."}

nlp_service = NlpService()
