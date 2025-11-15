import logging
import pandas as pd
from typing import List
import numpy as np
import json

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from src.db.models import BurnoutPrediction, EmployeeFeatures, Employee
from src.db.session import get_db

from .models import TeamPulseResponse, EmployeePulse, ExplanationResponse
from src.ai_services.prediction_service import prediction_service
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
        limit: int = Query(10, ge=1, le=50, description="Максимум топиков"),
        db: AsyncSession = Depends(get_db)
):
    # ... (этот эндпоинт не использовал мок-фичи, оставляем без изменений)
    repo = SQLiteRepository(db)
    employee = await repo.get_employee(telegram_id=telegram_id)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Сотрудник с telegram_id {telegram_id} не найден.")

    result = await db.execute(
        select(BurnoutPrediction)
        .where(BurnoutPrediction.user_id == employee.id)
        .order_by(desc(BurnoutPrediction.id))
        .limit(1)
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(status_code=404, detail="Анализ не найден")

    return {
        "telegram_id": telegram_id,
        "topics": prediction.topics_from_dialogues[:limit],
        "probability": prediction.probability_of_burnout
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