import logging
import uuid
import pandas as pd
from typing import List
import numpy as np

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from ...db.models import BurnoutPrediction
from ...db.session import get_db

from .models import TeamPulseResponse, EmployeePulse, ExplanationResponse
from ...ai_services.prediction_service import prediction_service
from ...db.repo import SQLiteRepository
from ...db.session import get_db

# Раскомментировать, когда FeatureService будет реализован
# from ...ai_services.feature_service import feature_service

logger = logging.getLogger(__name__)
router = APIRouter()

# =================================================================================
# ВРЕМЕННОЕ РЕШЕНИЕ: Кэш для сопоставления токенов и ID сотрудников.
# В продакшене это нужно заменить на Redis или другую быструю key-value базу.
# Сейчас кэш будет очищаться при каждом запросе к /team-pulse.
token_to_employee_id_cache = {}


# =================================================================================


@router.get("/dashboard/team-pulse", response_model=TeamPulseResponse, summary="Пульс Команды")
async def get_team_pulse(db: AsyncSession = Depends(get_db)):
    global token_to_employee_id_cache
    token_to_employee_id_cache.clear()  # Очищаем старые токены при каждом запросе

    repo = SQLiteRepository(db)
    try:

        # Получаем из БД список всех сотрудников
        all_employees = await repo.get_all_employees()
        if not all_employees:
            raise HTTPException(status_code=404, detail="Сотрудники не найдены.")

        employee_pulses: List[EmployeePulse] = []
        total_risk_score = 0
        risk_distribution = {"low": 0, "medium": 0, "high": 0}

        for employee in all_employees:
            # Собираем фичи для сотрудника (пока используется мок)
            # features = await feature_service.build_features_for_employee(employee.id)
            features = pd.DataFrame([{"age": 30, "days_since_vacation": employee.id * 50}])

            # Предсказываем вероятность
            probability = await prediction_service.predict_proba(features)

            # Сгенерируем токен и сохранить в кэш
            token = str(uuid.uuid4())
            token_to_employee_id_cache[token] = employee.id

            employee_pulses.append(EmployeePulse(token=token, risk_probability=probability))

            # Агрегируем результаты
            total_risk_score += probability
            if probability < 0.4:
                risk_distribution["low"] += 1
            elif probability < 0.7:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["high"] += 1

        overall_score = total_risk_score / len(all_employees) if all_employees else 0

        # Реализовать логику расчета реальной динамики
        mock_dynamics = f"+{round(np.random.uniform(1, 9))}%"

        # Формируем и возвращаем ответ в соответствии с моделью
        return TeamPulseResponse(
            overall_risk_score=overall_score,
            risk_dynamics_weekly=mock_dynamics,
            distribution=risk_distribution,
            employees=employee_pulses
        )

    except Exception as e:
        logger.error(f"Ошибка при получении пульса команды: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


@router.get("/dashboard/employees/{employee_token}/explain", response_model=ExplanationResponse,
            summary="Объяснение Риска")
async def get_prediction_explanation(employee_token: str):
    try:
        # Найдем реальный employee_id по токену из временного кэша
        employee_id = token_to_employee_id_cache.get(employee_token)
        if not employee_id:
            raise HTTPException(status_code=404, detail="Токен сотрудника не найден или устарел. Обновите дашборд.")

        # Соберем фичи для этого сотрудника (пока используется мок)
        # features = await feature_service.build_features_for_employee(employee_id)
        features = pd.DataFrame([{"age": 35, "days_since_last_vacation": 280}])

        # Вызовем сервис для получения объяснения
        explanation_data = await prediction_service.explain(features)

        if "error" in explanation_data:
            raise HTTPException(status_code=503, detail="Сервис предсказаний временно недоступен.")

        return ExplanationResponse(token=employee_token, **explanation_data)

    except HTTPException as e:
        # Пробрасываем HTTP исключения, чтобы не маскировать их под 500
        raise e
    except Exception as e:
        logger.error(f"Ошибка при объяснении предсказания для токена {employee_token}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


# =================================================================================
# Реализация WebSocket
# =================================================================================

class ConnectionManager:
    def __init__(self):
        # В будущем можно сделать словарь по team_id: List[WebSocket]
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)


# Создаем единственный экземпляр менеджера, который будет использоваться во всем приложении
manager = ConnectionManager()


@router.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Просто ждем сообщений, чтобы держать соединение открытым
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Клиент WebSocket отсоединился.")


@router.post("/internal/notify-risk-update", include_in_schema=False)
async def notify_risk_update(update_data: dict):
    # update_data должен содержать {'token': '...', 'new_risk_probability': 0.88}
    await manager.broadcast({
        "event_type": "EMPLOYEE_RISK_UPDATED",
        "payload": update_data
    })
    return {"status": "ok"}

@router.get("/dashboard/employees/{employee_token}/topics")
async def get_employee_topics(
    employee_token: str,
    limit: int = Query(10, ge=1, le=50, description="Максимум топиков"),
    db: AsyncSession = Depends(get_db)
):
    user_id = token_to_employee_id_cache.get(employee_token)
    if not user_id:
        raise HTTPException(404, "Токен не найден")
    result = await db.execute(
        select(BurnoutPrediction)
        .where(BurnoutPrediction.user_id == user_id)
        .order_by(desc(BurnoutPrediction.id))
        .limit(1)
    )
    prediction = result.scalar_one_or_none()
    if not prediction:
        raise HTTPException(404, "Анализ не найден")
    return {
        "token": employee_token,
        "topics": prediction.topics_from_dialogues[:limit],
        "probability": prediction.probability_of_burnout
    }