import logging
import pandas as pd
from typing import List
import numpy as np
import json

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from collections import Counter
from src.db.models import BurnoutPrediction, EmployeeFeatures, Employee, DialogueAnalysis, DialogueSession
from src.db.session import get_db

from .models import TeamPulseResponse, EmployeePulse, ExplanationResponse, ChatMessage, ChatRequest, ChatResponse
from src.ai_services.prediction_service import prediction_service
from src.ai_services.base import AiHelper, ChatLM
from src.db.repo import SQLiteRepository

# Раскомментировать, когда FeatureService будет реализован
# from ...ai_services.feature_service import feature_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =================================================================================
def convert_numpy_types(obj):
    # ... (функция без изменений)
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    elif hasattr(obj, "item"):
        return obj.item()
    else:
        return obj


# ДОБАВЛЕНО: Вспомогательная функция для конвертации фичей в DataFrame
def features_to_dataframe(features_obj: EmployeeFeatures) -> pd.DataFrame:
    """Конвертирует объект EmployeeFeatures в pd.DataFrame для модели."""
    if not features_obj:
        return pd.DataFrame()
    # Собираем словарь из атрибутов объекта
    feature_dict = {c.name: [getattr(features_obj, c.name)] for c in features_obj.__table__.columns if
                    c.name not in ['id', 'employee_id', 'created_at']}
    return pd.DataFrame(feature_dict)


@router.get("/dashboard/team-pulse", response_model=TeamPulseResponse, summary="Пульс Команды")
async def get_team_pulse(db: AsyncSession = Depends(get_db)):
    logger.info('Запуск get_team_pulse')
    repo = SQLiteRepository(db)
    try:
        logger.info('Получение всех сотрудников из БД')
        all_employees = await repo.get_all_employees()
        if not all_employees:
            raise HTTPException(status_code=404, detail="Сотрудники не найдены.")

        employee_pulses: List[EmployeePulse] = []
        total_risk_score = 0
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        processed_employees_count = 0

        for employee in all_employees:
            # ИЗМЕНЕНО: Получаем фичи из БД вместо мока
            latest_features = await repo.get_latest_features(employee.id)

            if not latest_features:
                logger.warning(f"Для сотрудника {employee.telegram_id} отсутствуют фичи. Пропускаем.")
                continue

            features = features_to_dataframe(latest_features)

            # Если у сотрудника нет фичей, мы его пропускаем
            if features.empty:
                continue

            probability = await prediction_service.predict_proba(features)

            # Используем sentiment_trend_last_90d из реальных фичей
            sentiment_trend = latest_features.sentiment_trend_last_90d if latest_features.sentiment_trend_last_90d is not None else 0.0

            employee_pulses.append(EmployeePulse(
                telegram_id=str(employee.telegram_id),
                risk_probability=probability,
                sentiment_trend=sentiment_trend
            ))

            processed_employees_count += 1
            total_risk_score += probability
            if probability < 0.4:
                risk_distribution["low"] += 1
            elif probability < 0.7:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["high"] += 1

        overall_score = total_risk_score / processed_employees_count if processed_employees_count > 0 else 0

        average_sentiment_all_time = await repo.get_average_sentiment_for_period()

        # Поле risk_dynamics_weekly теперь будет отображать это среднее значение, а не динамику.
        # Это значение будет строкой.
        if average_sentiment_all_time is not None:
            # Форматируем значение, например, до 2 знаков после запятой
            overall_sentiment_str = f"{average_sentiment_all_time:.2f}"
        else:
            # Значение по умолчанию, если анализов еще нет
            overall_sentiment_str = "0.0"


        return TeamPulseResponse(
            overall_risk_score=overall_score,
            risk_dynamics_weekly=overall_sentiment_str,
            distribution=risk_distribution,
            employees=employee_pulses
        )

    except Exception as e:
        logger.error(f"Ошибка при получении пульса команды: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


@router.get("/dashboard/employees/{telegram_id}/explain", response_model=ExplanationResponse,
            summary="Объяснение Риска")
async def get_prediction_explanation(telegram_id: int, db: AsyncSession = Depends(get_db)):
    try:
        repo = SQLiteRepository(db)
        employee = await repo.get_employee(telegram_id=telegram_id)
        if not employee:
            raise HTTPException(status_code=404, detail=f"Сотрудник с telegram_id {telegram_id} не найден.")

        # ИЗМЕНЕНО: Получаем фичи из БД вместо мока
        latest_features = await repo.get_latest_features(employee.id)
        if not latest_features:
            raise HTTPException(status_code=404, detail=f"Фичи для сотрудника {telegram_id} не найдены.")

        features = features_to_dataframe(latest_features)

        explanation_data = await prediction_service.explain(features)
        if "error" in explanation_data:
            raise HTTPException(status_code=503, detail="Сервис предсказаний временно недоступен.")

        explanation_data = convert_numpy_types(explanation_data)

        return ExplanationResponse(telegram_id=str(telegram_id), **explanation_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Ошибка при объяснении предсказания для telegram_id {telegram_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


# ... (Код WebSocket остается без изменений) ...
class ConnectionManager:
    # ...
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except RuntimeError:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    # ...
    await manager.connect(websocket)
    logger.info("Новый клиент WebSocket подключился.")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Получено сообщение от бота по WebSocket: {data}")
            try:
                message_data = json.loads(data)
                await manager.broadcast(message_data)
                logger.info(f"Сообщение разослано {len(manager.active_connections)} клиентам.")
            except json.JSONDecodeError:
                logger.warning(f"Получено некорректное JSON-сообщение, оно будет проигнорировано: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Клиент WebSocket отсоединился.")


@router.get("/dashboard/employees/{telegram_id}/topics")
async def get_employee_topics(
        telegram_id: int,
        limit: int = Query(10, ge=1, le=50, description="Максимум топиков"), # Параметр больше не используется, но оставлен для совместимости
        db: AsyncSession = Depends(get_db)
):
    repo = SQLiteRepository(db)
    employee = await repo.get_employee(telegram_id=telegram_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Сотрудник с telegram_id {telegram_id} не найден.")

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---

    # ИЗМЕНЕНО: Запрос теперь идет к DialogueAnalysis через DialogueSession,
    # чтобы найти самый свежий анализ для данного сотрудника.
    result = await db.execute(
        select(DialogueAnalysis)
        .join(DialogueSession, DialogueAnalysis.session_id == DialogueSession.id)
        .where(DialogueSession.employee_id == employee.id)
        .order_by(desc(DialogueSession.created_at)) # Сортируем по дате сессии
        .limit(1)
    )
    analysis = result.scalar_one_or_none() # Получаем объект DialogueAnalysis

    if not analysis:
        raise HTTPException(status_code=404, detail="Анализ для сотрудника не найден")

    # ИЗМЕНЕНО: Формируем ответ на основе данных из DialogueAnalysis
    return {
        "telegram_id": telegram_id,
        "topics": analysis.comment,  # Теперь это одна строка из поля comment
        "sentiment": analysis.sentiment, # Добавлено для контекста
        "is_burnout_risk_detected": analysis.is_burnout_risk_detected # Добавлено для контекста
    }


@router.get("/dashboard/employees/{telegram_id}/prediction",
            summary="Получить свежую предикцию для сотрудника (через CatBoost)")
async def get_prediction(
        telegram_id: int,
        db: AsyncSession = Depends(get_db)
):
    repo = SQLiteRepository(db)
    employee = await repo.get_employee(telegram_id=telegram_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Сотрудник с telegram_id {telegram_id} не найден.")

    try:
        # ИЗМЕНЕНО: Получаем фичи из БД вместо мока
        latest_features = await repo.get_latest_features(employee.id)
        if not latest_features:
            raise HTTPException(status_code=404, detail=f"Фичи для сотрудника {telegram_id} не найдены.")

        features = features_to_dataframe(latest_features)

        probability = await prediction_service.predict_proba(features)

        return {
            "telegram_id": telegram_id,
            "probability": probability,
        }

    except Exception as e:
        logger.error(f"Ошибка при выполнении предсказания для telegram_id {telegram_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503,
                            detail=f"Сервис предсказаний недоступен или произошла внутренняя ошибка: {e}")


@router.get("/dashboard/employees/{telegram_id}/what-if/vacation",
            summary="Что если: Отправить в отпуск")
async def get_what_if_vacation_prediction(
        telegram_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Рассчитывает "что если" сценарий: какой будет вероятность выгорания,
    если сбросить счетчик дней с последнего отпуска до нуля.
    """
    logger.info(f"Запуск 'что если' сценария для telegram_id {telegram_id}")
    repo = SQLiteRepository(db)
    employee = await repo.get_employee(telegram_id=telegram_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Сотрудник с telegram_id {telegram_id} не найден.")

    try:
        # 1. Получаем самые свежие фичи из БД
        latest_features = await repo.get_latest_features(employee.id)
        if not latest_features:
            raise HTTPException(status_code=404, detail=f"Фичи для сотрудника {telegram_id} не найдены.")

        # 2. Получаем текущую (оригинальную) вероятность
        original_features_df = features_to_dataframe(latest_features)
        original_probability = await prediction_service.predict_proba(original_features_df)

        # 3. Создаем копию фичей и изменяем ее
        # Мы используем ту же функцию, чтобы создать новый DataFrame, который можно безопасно менять
        what_if_features_df = features_to_dataframe(latest_features)

        # Проверяем, есть ли вообще такая колонка в DataFrame, чтобы избежать ошибок
        if 'days_since_last_vacation' in what_if_features_df.columns:
            logger.info(f"Изменение 'days_since_last_vacation' на 0 для 'что если' сценария.")
            what_if_features_df['days_since_last_vacation'] = 0
        else:
            logger.warning("Колонка 'days_since_last_vacation' не найдена в фичах. Предсказание будет таким же.")

        # 4. Получаем новую ("что если") вероятность
        what_if_probability = await prediction_service.predict_proba(what_if_features_df)

        # 5. Возвращаем оба результата для сравнения
        return {
            "telegram_id": telegram_id,
            "original_probability": original_probability,
            "what_if_vacation_probability": what_if_probability,
            "probability_change": what_if_probability - original_probability
        }

    except Exception as e:
        logger.error(f"Ошибка при выполнении 'что если' предсказания для telegram_id {telegram_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503,
                            detail=f"Сервис предсказаний недоступен или произошла внутренняя ошибка: {e}")


@router.get("/llm_helper", summary="AI-помощник для анализа команды")
async def get_llm_recommendation(db: AsyncSession = Depends(get_db)):
    """
    Собирает общую статистику по команде и самые частые темы для обсуждения,
    отправляет их AI-помощнику и возвращает его рекомендации.
    """
    logger.info("Запуск AI-помощника")
    repo = SQLiteRepository(db)
    try:
        # --- ШАГ 1: Получаем данные, аналогичные TeamPulse ---
        all_employees = await repo.get_all_employees()
        if not all_employees:
            raise HTTPException(status_code=404, detail="Сотрудники не найдены.")

        total_risk_score = 0
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        processed_employees_count = 0

        for employee in all_employees:
            latest_features = await repo.get_latest_features(employee.id)
            if not latest_features:
                continue

            features = features_to_dataframe(latest_features)
            if features.empty:
                continue

            probability = await prediction_service.predict_proba(features)
            processed_employees_count += 1
            total_risk_score += probability
            if probability < 0.4:
                risk_distribution["low"] += 1
            elif probability < 0.7:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["high"] += 1

        overall_score = total_risk_score / processed_employees_count if processed_employees_count > 0 else 0

        # Собираем статистику в словарь
        team_pulse_data = {
            "overall_risk_score": overall_score,
            "risk_distribution": risk_distribution,
            "processed_employees_count": processed_employees_count,
        }

        # --- ШАГ 2: Получаем и обрабатываем топики (комментарии) ---
        all_comments = await repo.get_all_latest_analysis_comments()

        # Убираем пустые комментарии и считаем самые частые
        valid_comments = [comment for comment in all_comments if comment and comment.strip()]

        if not valid_comments:
            top_topics = []
        else:
            topic_counts = Counter(valid_comments)
            # most_common возвращает список кортежей ('тема', количество)
            top_topics_with_counts = topic_counts.most_common(7)
            # Нам нужны только сами темы (строки)
            top_topics = [topic for topic, count in top_topics_with_counts]

        # --- ШАГ 3: Вызываем AI-помощника ---
        logger.info(f"Отправка данных AI-помощнику. Статистика: {team_pulse_data}, Топики: {top_topics}")
        ai_helper = AiHelper()

        # Форматируем данные для промпта
        team_pulse_json = json.dumps(team_pulse_data, indent=2, ensure_ascii=False)

        # Получаем рекомендацию от LLM
        ai_recommendation = await ai_helper.help(
            team_pulse=team_pulse_json,
            topics=top_topics
        )

        # --- ШАГ 4: Возвращаем ответ ---
        return {"recommendation": ai_recommendation}

    except Exception as e:
        logger.error(f"Ошибка при работе AI-помощника: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при получении рекомендации от AI.")


@router.post("/llm_helper/chat", response_model=ChatResponse, summary="Интерактивный AI-чат")
async def handle_chat_completion(request: ChatRequest):
    """
    Принимает историю сообщений и возвращает следующий ответ от LLM.
    Поддерживает непрерывный диалог.
    """
    logger.info(f"Получен запрос в AI-чат. История содержит {len(request.history)} сообщений.")

    try:
        # 1. Инициализируем ChatLM, который предназначен для диалогов
        chat_lm = AiHelper()

        # 2. Конвертируем Pydantic модели в словари, которые ожидает ChatLM
        # Pydantic v2 использует .model_dump(), если у вас v1, используйте .dict()
        try:
            conversation_history = [message.model_dump() for message in request.history]
            print(conversation_history)
        except AttributeError:
            # Для Pydantic v1
            conversation_history = [message.dict() for message in request.history]

        # 3. Получаем ответ от языковой модели
        logger.info("Отправка истории сообщений в ChatLM для генерации ответа.")
        ai_response = await chat_lm.get_response(conversation_history)
        logger.info("Ответ от ChatLM успешно получен.")

        # 4. Возвращаем ответ в ожидаемом формате
        return ChatResponse(response=ai_response)

    except Exception as e:
        logger.error(f"Ошибка при обработке чат-комплишена: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при работе с AI-чатом.")
