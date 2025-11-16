import logging
import os
import pandas as pd
from catboost import CatBoostClassifier
import shap
from ..settings import settings

logger = logging.getLogger(__name__)

MODEL_FILE = "models/catboost.cbm"


class PredictionService:
    model: CatBoostClassifier = None
    explainer: shap.TreeExplainer = None

    def __init__(self):
        if PredictionService.model is None:
            logger.info(f"Загрузка модели CatBoost из файла: {MODEL_FILE}")
            if not os.path.exists(MODEL_FILE):
                logger.error(f"ФАЙЛ МОДЕЛИ НЕ НАЙДЕН: {MODEL_FILE}. Запустите ноутбук для обучения.")
                raise FileNotFoundError(f"Model file not found at {MODEL_FILE}")
            else:
                PredictionService.model = CatBoostClassifier()
                PredictionService.model.load_model(MODEL_FILE)
                logger.info("Модель CatBoost успешно загружена.")

                PredictionService.explainer = shap.TreeExplainer(self.model)
                logger.info("SHAP Explainer успешно инициализирован.")

    async def predict_proba(self, features: pd.DataFrame) -> float:
        if self.model is None:
            logger.warning("Модель не загружена, возвращается заглушка.")
            return 0.5

        prediction = self.model.predict_proba(features)[0, 1]
        return float(prediction)

    async def explain(self, features: pd.DataFrame) -> dict:
        if self.model is None or self.explainer is None:
            logger.warning("Модель/Explainer не загружены, возвращается заглушка.")
            return {"error": "Модель не готова"}

        burnout_probability = await self.predict_proba(features)

        shap_values = self.explainer.shap_values(features)

        explanation = {
            "burnout_probability": burnout_probability,
            "shap_explanation": {
                "base_value": self.explainer.expected_value,
                "factors": []
            }
        }

        for i, feature_name in enumerate(features.columns):
            explanation["shap_explanation"]["factors"].append({
                "feature": feature_name,
                "value": features[feature_name].iloc[0],
                "contribution": shap_values[0, i]
            })

        explanation["shap_explanation"]["factors"].sort(key=lambda x: abs(x["contribution"]), reverse=True)

        return explanation


prediction_service = PredictionService()
