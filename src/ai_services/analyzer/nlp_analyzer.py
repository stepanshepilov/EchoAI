import logging
from typing import Dict, Any, List
import json
from pydantic import BaseModel, Field, ValidationError 
from ..prompts.nlp_analyzer import SYSTEM_PROMPT_ANALYZER, TOPICS_ANALAYZER_PROMPT
from ..base import BaseLM

logger = logging.getLogger(__name__)

class SentimentAnalysisResponse(BaseModel):
    sentiment: float = Field(
        ..., 
        description="Эмоциональный тон по шкале от -1.0 (крайне негативный, выгорание) до 1.0 (позитивный, энергия).",
        ge=-1.0, 
        le=1.0
    )
    is_burnout_risk_detected : bool = Field(
        ...,
        description="Флаг, указывающий на прямые или косвенные признаки выгорания в тексте (True/False)."
    )


class Topic(BaseModel):
    topic: str
    category: str
    mentions: int
    sentiment: float
    importance: float
    examples: List[str]

class StructuredTopicsResponse(BaseModel):
    comment: List[Topic] = Field(..., description="Список выявленных тем и проблем.")

class NlpService(BaseLM):
    def __init__(self):
        super().__init__()

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        system_prompt = SYSTEM_PROMPT_ANALYZER
        user_prompt = f"Проанализируй следующий текст и верни результат в JSON формате: '{text}'"

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
            
            return validated_data.model_dump()

        except ValidationError as e:
            logger.error(f"Ошибка валидации ответа LLM: {e}. Ответ модели: '{response_content}'")
            return {"error": "Некорректный формат ответа от LLM."}
        except Exception as e:
            logger.error(f"Критическая ошибка при анализе текста LLM: {e}", exc_info=True)
            return {"error": "Внутренняя ошибка сервиса NLP."}
        
        

    async def analyze_topics(self, text: str) -> Dict[str, Any]:
        """
        Анализирует текст и возвращает ТОЛЬКО структурированный список тем 
        под ключом 'comment'. Вся логика находится внутри этой функции.
        """
        system_prompt = TOPICS_ANALAYZER_PROMPT
        user_prompt = f"Проанализируй следующий текст и верни результат в JSON формате, как указано в системных инструкциях: '{text}'"
        
        response_content = "" # Инициализируем переменную на случай ошибки до вызова API
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
            
            validated_data = StructuredTopicsResponse.model_validate_json(response_content)
            
            return validated_data.model_dump()
    
        except (ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка валидации или парсинга JSON от LLM: {e}. Ответ модели: '{response_content}'")
            return {"error": "Некорректный формат ответа от LLM."}
        
        # Эта ошибка сработает при проблемах с сетью, API и других непредвиденных сбоях
        except Exception as e:
            logger.error(f"Критическая ошибка при вызове LLM: {e}", exc_info=True)
            return {"error": "Внутренняя ошибка сервиса NLP."}

nlp_service = NlpService()
