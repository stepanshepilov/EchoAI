# Содержимое файла: src/ai_services/feature_service.py

import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.repo import SQLiteRepository


class FeatureService:
    async def build_features_for_employee(self, employee_id: int, db: AsyncSession) -> pd.DataFrame:
        """
        Собирает и рассчитывает фичи для сотрудника из базы данных.
        """
        repo = SQLiteRepository(db)
        now = datetime.utcnow()

        # 1. Расчет фичей на основе Sentiment из диалогов
        # Рассчитываем средний sentiment за последние 30, 90 и 365 дней
        sentiment_30d = await repo.get_sentiment_stats_for_period(employee_id, now - timedelta(days=30), now)
        sentiment_90d = await repo.get_sentiment_stats_for_period(employee_id, now - timedelta(days=90), now)
        sentiment_365d = await repo.get_sentiment_stats_for_period(employee_id, now - timedelta(days=365), now)

        # Рассчитываем тренд сентимента за последние 90 дней
        # (сравниваем первую половину периода со второй)
        sentiment_90d_first_half = await repo.get_sentiment_stats_for_period(
            employee_id, now - timedelta(days=90), now - timedelta(days=45)
        )
        sentiment_90d_second_half = await repo.get_sentiment_stats_for_period(
            employee_id, now - timedelta(days=45), now
        )
        # Тренд - это разница между сентиментом второй и первой половины
        sentiment_trend_90d = sentiment_90d_second_half - sentiment_90d_first_half

        # 2. Сборка всех фичей в словарь
        # ВНИМАНИЕ: Большинство фичей ниже - это МОКИ, так как данных о них нет в вашей БД.
        # Их нужно будет заменить на запросы к реальным системам (HR, Jira и т.д.), когда они появятся.
        feature_dict = {
            # --- Демографические данные (TODO: получать из HR-системы) ---
            "age": 30,
            "gender": 1,
            "tenure_months": 24,  # Стаж в месяцах

            # --- Данные о задачах (TODO: получать из таск-трекера) ---
            "tasks_completed_last_30d": 10,
            "tasks_failed_last_30d": 1,
            "tasks_completed_last_90d": 30,
            "tasks_failed_last_90d": 3,
            "tasks_completed_last_365d": 120,
            "tasks_failed_last_365d": 10,

            # --- Данные об отсутствиях (TODO: получать из HR-системы) ---
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

            # --- РАССЧИТАННЫЕ ФИЧИ ИЗ НАШЕЙ БД ---
            "avg_sentiment_last_30d": sentiment_30d,
            "avg_sentiment_last_90d": sentiment_90d,
            "avg_sentiment_last_365d": sentiment_365d,
            "sentiment_trend_last_90d": sentiment_trend_90d,
        }

        # 3. Создание DataFrame, который ожидает модель
        return pd.DataFrame([feature_dict])


# Создаем единственный экземпляр сервиса для использования в API
feature_service = FeatureService()