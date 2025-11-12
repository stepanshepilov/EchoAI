import logging
from fastapi import APIRouter, HTTPException, Query
from .models import TeamPulseResponse, ExplanationResponse
from ...ai_services.prediction_service import prediction_service
import pandas as pd
# from ..services.feature_service import feature_service
# from db.repository import db_repository

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/team-pulse", response_model=TeamPulseResponse, summary="Получить 'пульс' команды")
async def get_team_pulse(team_id: str = Query(..., description="ID команды для анализа")):
    try:
        # employees = await db_repository.get_employees_by_team(team_id)
        # features = await feature_service.build_features_for_employees(employees)
        # predictions = await prediction_service.predict_batch(features)
        mock_response = {
            "team_id": team_id,
            "overall_risk_score": 0.45,
            "risk_dynamics_weekly": "+5%",
            "distribution": {"low": 10, "medium": 5, "high": 3},
            "employees": [
                {"token": "a1b2-c3d4", "risk_probability": 0.85, "sentiment_trend": -0.3},
                {"token": "e5f6-g7h8", "risk_probability": 0.21, "sentiment_trend": 0.1},
            ]
        }
        return TeamPulseResponse(**mock_response)

    except Exception as e:
        logger.error(f"Ошибка при получении пульса команды {team_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")


@router.get("/employees/{employee_token}/explain", response_model=ExplanationResponse, summary="Объяснить предсказание для сотрудника")
async def get_prediction_explanation(employee_token: str):
    try:
        # employee = await db_repository.get_employee_by_token(employee_token)
        # features = await feature_service.build_features_for_employee(employee)
        # explanation = await prediction_service.explain(features)
        mock_response = {
            "token": employee_token,
            "burnout_probability": 0.85,
            "shap_explanation": {
                "base_value": 0.35,
                "factors": [
                    {"feature": "days_since_last_vacation", "value": 280, "contribution": 0.25},
                    {"feature": "avg_sentiment_last_30d", "value": -0.6, "contribution": 0.18},
                ]
            }
        }
        return ExplanationResponse(**mock_response)

    except Exception as e:
        logger.error(f"Ошибка при объяснении предсказания для токена {employee_token}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

@router.get("/employees/{employee_token}/explain", response_model=ExplanationResponse)
async def get_prediction_explanation(employee_token: str):
    # features_df = await feature_service.build_features_for_employee(employee_token)
    mock_features = pd.DataFrame([{"age": 35, "days_since_last_vacation": 280}])

    explanation_data = await prediction_service.explain(mock_features)

    if "error" in explanation_data:
        raise HTTPException(status_code=503, detail="Сервис предсказаний недоступен.")
        
    return ExplanationResponse(token=employee_token, **explanation_data)
