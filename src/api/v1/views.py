import logging
import pandas as pd
from typing import List
import json

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from collections import Counter
from src.db.models import EmployeeFeatures, DialogueAnalysis, DialogueSession
from src.db.session import get_db

from .models import TeamPulseResponse, EmployeePulse, ExplanationResponse, ChatResponse, ChatRequest
from src.ai_services.prediction_service import prediction_service
from src.ai_services.base import AiHelper
from src.db.repo import SQLiteRepository


logger = logging.getLogger(__name__)
router = APIRouter()


def convert_numpy_types(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    elif hasattr(obj, "item"):
        return obj.item()
    else:
        return obj


def features_to_dataframe(features_obj: EmployeeFeatures) -> pd.DataFrame:
    """Конвертирует объект EmployeeFeatures в pd.DataFrame для модели."""
    if not features_obj:
        return pd.DataFrame()
    feature_dict = {c.name: [getattr(features_obj, c.name)] for c in features_obj.__table__.columns if
                    c.name not in ['id', 'employee_id', 'created_at']}
    return pd.DataFrame(feature_dict)


@router.get(
    "/dashboard/team-pulse",
    response_model=TeamPulseResponse,
    summary="Пульс Команды"
)
async def get_team_pulse(db: AsyncSession = Depends(get_db)):
    repo = SQLiteRepository(db)
    
    try:
        all_employees = await repo.get_all_employees()
        logger.info(f"Получено сотрудников из БД: {len(all_employees)}")
        
        if not all_employees:
            raise HTTPException(status_code=404, detail="Сотрудники не найдены.")

        employee_pulses: List[EmployeePulse] = []
        total_risk_score = 0
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        processed_employees_count = 0

        for employee in all_employees:
            latest_features = await repo.get_latest_features(employee.id)

            if not latest_features:
                logger.warning(
                    f"⚠️ Для сотрудника {employee.telegram_id} отсутствуют фичи. "
                    f"Используем дефолтные значения."
                )
                probability = 0.5
                
                last_session = await repo.get_last_session_for_employee(employee.id)
                if last_session:
                    result = await db.execute(
                        select(DialogueAnalysis)
                        .where(DialogueAnalysis.session_id == last_session.id)
                    )
                    analysis = result.scalar_one_or_none()
                    sentiment_trend = analysis.sentiment if analysis and analysis.sentiment is not None else 0.0
                else:
                    sentiment_trend = 0.0
                
            else:
                features = features_to_dataframe(latest_features)
                
                if features.empty:
                    probability = 0.5
                    sentiment_trend = 0.0
                else:
                    probability = await prediction_service.predict_proba(features)
                    sentiment_trend = (
                        latest_features.sentiment_trend_last_90d 
                        if latest_features.sentiment_trend_last_90d is not None 
                        else 0.0
                    )

            employee_pulses.append(
                EmployeePulse(
                    telegram_id=str(employee.telegram_id),
                    risk_probability=probability,
                    sentiment_trend=sentiment_trend
                )
            )

            processed_employees_count += 1
            total_risk_score += probability
            if probability < 0.4:
                risk_distribution["low"] += 1
            elif probability < 0.7:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["high"] += 1

        overall_score = (
            total_risk_score / processed_employees_count 
            if processed_employees_count > 0 
            else 0
        )
        
        average_sentiment_all_time = await repo.get_average_sentiment_for_period()
        overall_sentiment_str = (
            f"{average_sentiment_all_time:.2f}" 
            if average_sentiment_all_time is not None 
            else "0.0"
        )

        return TeamPulseResponse(
            overall_risk_score=overall_score,
            risk_dynamics_weekly=overall_sentiment_str,
            distribution=risk_distribution,
            employees=employee_pulses
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении пульса команды: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


@router.get(
    "/dashboard/employees/{telegram_id}/explain",
    response_model=ExplanationResponse,
    summary="Объяснение Риска"
)
async def get_prediction_explanation(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        repo = SQLiteRepository(db)
        employee = await repo.get_employee(telegram_id=telegram_id)
        
        if not employee:
            raise HTTPException(
                status_code=404,
                detail=f"Сотрудник с telegram_id {telegram_id} не найден."
            )

        latest_features = await repo.get_latest_features(employee.id)
        
        if not latest_features:
            logger.warning(
                f"⚠️ Фичи для сотрудника {telegram_id} отсутствуют. "
                f"Возвращаем дефолтное объяснение."
            )
            return ExplanationResponse(
                telegram_id=str(telegram_id),
                burnout_probability=0.5,
                shap_explanation={
                    "base_value": 0.5,
                    "factors": [
                        {
                            "feature": "Данные обрабатываются",
                            "value": "N/A",
                            "contribution": 0.0
                        }
                    ]
                }
            )

        features = features_to_dataframe(latest_features)
        
        if features.empty:
            logger.warning(
                f"⚠️ DataFrame фичей для сотрудника {telegram_id} пустой. "
                f"Возвращаем дефолтное объяснение."
            )
            return ExplanationResponse(
                telegram_id=str(telegram_id),
                burnout_probability=0.5,
                shap_explanation={
                    "base_value": 0.5,
                    "factors": [
                        {
                            "feature": "Данные обрабатываются",
                            "value": "N/A",
                            "contribution": 0.0
                        }
                    ]
                }
            )

        explanation_data = await prediction_service.explain(features)
        
        if "error" in explanation_data:
            raise HTTPException(
                status_code=503,
                detail="Сервис предсказаний временно недоступен."
            )

        explanation_data = convert_numpy_types(explanation_data)
        return ExplanationResponse(telegram_id=str(telegram_id), **explanation_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка при объяснении предсказания для telegram_id {telegram_id}: {e}",
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


class ConnectionManager:
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
    repo = SQLiteRepository(db)
    employee = await repo.get_employee(telegram_id=telegram_id)
    
    if not employee:
        raise HTTPException(
            status_code=404,
            detail=f"Сотрудник с telegram_id {telegram_id} не найден."
        )

    result = await db.execute(
        select(DialogueAnalysis)
        .join(DialogueSession, DialogueAnalysis.session_id == DialogueSession.id)
        .where(DialogueSession.employee_id == employee.id)
        .order_by(desc(DialogueSession.created_at))
        .limit(1)
    )
    analysis = result.scalar_one_or_none()

    if not analysis:
        logger.warning(
            f"⚠️ Анализ для сотрудника {telegram_id} не найден. "
            f"Возвращаем пустой массив топиков."
        )
        return {
            "telegram_id": telegram_id,
            "topics": [],
            "sentiment": 0.0,
            "is_burnout_risk_detected": False
        }

    try:
        import json
        
        if analysis.comment:
            try:
                parsed_comment = json.loads(analysis.comment)
            
                if isinstance(parsed_comment, list):
                    topics = parsed_comment
                elif isinstance(parsed_comment, dict):
                    topics = parsed_comment.get('topics') or parsed_comment.get('main_topics') or []
                else:
                    topics = [{
                        "topic": str(parsed_comment),
                        "sentiment": analysis.sentiment or 0.0,
                        "mentions": 1,
                        "examples": [str(parsed_comment)]
                    }]

            except (json.JSONDecodeError, TypeError):
                topics = [{
                    "topic": analysis.comment,
                    "sentiment": analysis.sentiment or 0.0,
                    "mentions": 1,
                    "examples": [analysis.comment]
                }]
        else:
            topics = []
        
        formatted_topics = []
        for topic in topics:
            if isinstance(topic, dict):
                formatted_topics.append({
                    "topic": topic.get("topic", "Тема не указана"),
                    "sentiment": topic.get("sentiment", analysis.sentiment or 0.0),
                    "mentions": topic.get("mentions", 1),
                    "examples": topic.get("examples", [topic.get("topic", "")])
                })
            elif isinstance(topic, str):
                formatted_topics.append({
                    "topic": topic,
                    "sentiment": analysis.sentiment or 0.0,
                    "mentions": 1,
                    "examples": [topic]
                })
        
        return {
            "telegram_id": telegram_id,
            "topics": formatted_topics,
            "sentiment": analysis.sentiment,
            "is_burnout_risk_detected": analysis.is_burnout_risk_detected
        }
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге топиков для {telegram_id}: {e}", exc_info=True)

        return {
            "telegram_id": telegram_id,
            "topics": [],
            "sentiment": analysis.sentiment or 0.0,
            "is_burnout_risk_detected": analysis.is_burnout_risk_detected or False
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


@router.get(
    "/dashboard/employees/{telegram_id}/what-if/vacation",
    summary="Что если: Отправить в отпуск"
)
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
        raise HTTPException(
            status_code=404,
            detail=f"Сотрудник с telegram_id {telegram_id} не найден."
        )

    try:
        latest_features = await repo.get_latest_features(employee.id)
        
        # ✅ ИЗМЕНЕНО: Если нет фичей - возвращаем дефолтные значения
        if not latest_features:
            logger.warning(
                f"⚠️ Фичи для сотрудника {telegram_id} отсутствуют. "
                f"Возвращаем оценочные значения."
            )
            # Оценочные значения: отпуск снижает риск примерно на 20%
            return {
                "telegram_id": telegram_id,
                "original_probability": 0.5,      # Средний риск
                "what_if_vacation_probability": 0.3,  # После отпуска ниже
                "probability_change": -0.2        # Изменение на -20%
            }

        # Текущая вероятность
        original_features_df = features_to_dataframe(latest_features)
        
        if original_features_df.empty:
            logger.warning(
                f"⚠️ DataFrame фичей для сотрудника {telegram_id} пустой. "
                f"Возвращаем оценочные значения."
            )
            return {
                "telegram_id": telegram_id,
                "original_probability": 0.5,
                "what_if_vacation_probability": 0.3,
                "probability_change": -0.2
            }
        
        # ✅ Есть фичи - считаем нормально
        original_probability = await prediction_service.predict_proba(original_features_df)

        # Симуляция отпуска
        what_if_features_df = features_to_dataframe(latest_features)
        
        if 'days_since_last_vacation' in what_if_features_df.columns:
            logger.info("Изменение 'days_since_last_vacation' на 0 для 'что если' сценария.")
            what_if_features_df['days_since_last_vacation'] = 0
        else:
            logger.warning(
                "Колонка 'days_since_last_vacation' не найдена. "
                "Предсказание будет таким же."
            )

        what_if_probability = await prediction_service.predict_proba(what_if_features_df)

        return {
            "telegram_id": telegram_id,
            "original_probability": original_probability,
            "what_if_vacation_probability": what_if_probability,
            "probability_change": what_if_probability - original_probability
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка при выполнении 'что если' предсказания "
            f"для telegram_id {telegram_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=503,
            detail=f"Сервис предсказаний недоступен: {e}"
        )


@router.get("/llm_helper", summary="AI-помощник для анализа команды")
async def get_llm_recommendation(db: AsyncSession = Depends(get_db)):
    logger.info("Запуск AI-помощника")
    repo = SQLiteRepository(db)
    try:
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

        team_pulse_data = {
            "overall_risk_score": overall_score,
            "risk_distribution": risk_distribution,
            "processed_employees_count": processed_employees_count,
        }

        all_comments = await repo.get_all_latest_analysis_comments()

        valid_comments = [comment for comment in all_comments if comment and comment.strip()]

        if not valid_comments:
            top_topics = []
        else:
            topic_counts = Counter(valid_comments)
            top_topics_with_counts = topic_counts.most_common(7)
            top_topics = [topic for topic, count in top_topics_with_counts]

        ai_helper = AiHelper()

        team_pulse_json = json.dumps(team_pulse_data, indent=2, ensure_ascii=False)

        ai_recommendation = await ai_helper.help(
            team_pulse=team_pulse_json,
            topics=top_topics
        )

        return {"recommendation": ai_recommendation}

    except Exception as e:
        logger.error(f"Ошибка при работе AI-помощника: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при получении рекомендации от AI.")

@router.post("/llm_helper/chat", response_model=ChatResponse, summary="Интерактивный AI-чат")
async def handle_chat_completion(request: ChatRequest):
    try:
        chat_lm = AiHelper()

        try:
            conversation_history = [message.model_dump() for message in request.history]
            print(conversation_history)
        except AttributeError:
            conversation_history = [message.dict() for message in request.history]

        ai_response = await chat_lm.get_response(conversation_history)

        return ChatResponse(response=ai_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера при работе с AI-чатом.")
