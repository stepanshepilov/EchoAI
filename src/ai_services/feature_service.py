import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repo import SQLiteRepository


class FeatureService:
    async def build_features_for_employee(self, employee_id: int, db: AsyncSession) -> pd.DataFrame:
        feature_dict = {
            "age": 30,
            "gender": 1,
            "tenure_months": 24,
            "tasks_completed_last_30d": 10,
            "tasks_failed_last_30d": 1,
            "tasks_completed_last_90d": 30,
            "tasks_failed_last_90d": 3,
            "tasks_completed_last_365d": 120,
            "tasks_failed_last_365d": 10,
            "sick_leave_count_last_30d": 0,
            "short_sick_leaves_count_last_30d": 0,
            "total_sick_days_last_30d": 0,
            "sick_leave_count_last_90d": 1,
            "short_sick_leaves_count_last_90d": 1,
            "total_sick_days_last_90d": 2,
            "sick_leave_count_last_365d": 3,
            "short_sick_leaves_count_last_365d": 2,
            "total_sick_days_last_365d": 5,
            "days_since_last_vacation": 150,
            "avg_sentiment_last_30d": 0,
            "avg_sentiment_last_90d": 0,
            "avg_sentiment_last_365d": 0,
            "sentiment_trend_last_90d": 0,
        }

        return pd.DataFrame([feature_dict])


feature_service = FeatureService()
