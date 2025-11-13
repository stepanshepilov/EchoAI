import asyncio
import os
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine
from src.settings import settings
from src.db.models import Base, Employee, DialogueSession, ChatMessage, DialogueAnalysis, BurnoutPrediction

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MOCK_EMPLOYEES = [
    {"id": 1, "telegram_id": 111111111, 'name': 'Чувак 1', 'cdek_id': '123'},
    {"id": 2, "telegram_id": 222222222, 'name': 'Чувак 2', 'cdek_id': '334'},
    {"id": 3, "telegram_id": 333333333, 'name': 'Чувак 3', 'cdek_id': '445'},
]

MOCK_TOPICS = [
    [
        {
            "topic": "Переработки",
            "category": "workload",
            "mentions": 3,
            "sentiment": -0.6,
            "importance": 0.8,
            "examples": ["работаю по выходным", "засиживаюсь допоздна"]
        },
        {
            "topic": "Конфликт с коллегой",
            "category": "team_relations",
            "mentions": 2,
            "sentiment": -0.8,
            "importance": 0.6,
            "examples": ["постоянные споры", "не находим общий язык"]
        }
    ],
    [
        {
            "topic": "Недостаток признания",
            "category": "recognition",
            "mentions": 1,
            "sentiment": -0.3,
            "importance": 0.5,
            "examples": ["никто не замечает мои усилия"]
        }
    ],
    [
        {
            "topic": "Усталость",
            "category": "health",
            "mentions": 2,
            "sentiment": -0.7,
            "importance": 0.7,
            "examples": ["чувствую себя выжатым"]
        }
    ]
]

MOCK_SHAP = {
    "base_value": 0.35,
    "prediction_value": 0.85,
    "features": [
        {
            "feature_name": "days_since_last_vacation",
            "feature_value": 280,
            "shap_value": 0.25,
            "display_value": "280 дней",
            "category": "time_off"
        },
        {
            "feature_name": "avg_sentiment_last_30d",
            "feature_value": -0.6,
            "shap_value": 0.18,
            "display_value": "-60%",
            "category": "sentiment"
        }
    ],
    "top_risk_factors": ["days_since_last_vacation", "avg_sentiment_last_30d"],
    "top_protective_factors": []
}


async def seed_database():
    db_file = settings.DATABASE_URL.split('///')[-1]

    if os.path.exists(db_file):
        logger.info(f"Удаление старой базы данных: {db_file}")
        os.remove(db_file)

    engine = create_async_engine(settings.DATABASE_URL)

    logger.info("Создание таблиц в базе данных...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы успешно созданы.")

    from src.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        logger.info("Добавление моковых сотрудников...")
        for emp_data in MOCK_EMPLOYEES:
            employee = Employee(**emp_data)
            session.add(employee)
        await session.commit()
        logger.info(f"{len(MOCK_EMPLOYEES)} сотрудников добавлено.")

        logger.info("Создание моковой истории диалога...")
        for idx, emp in enumerate(MOCK_EMPLOYEES):
            emp_id = emp['id']
            session_id = str(uuid.uuid4())
            new_session = DialogueSession(id=session_id, employee_id=emp_id)
            session.add(new_session)

            messages = [
                ChatMessage(session_id=session_id, role='assistant', content='Привет! Это Эхо. Как прошла неделя?',
                            timestamp=datetime.utcnow() - timedelta(minutes=5)),
                ChatMessage(session_id=session_id, role='user', content='Привет. Неделя была тяжелая, много отчетов.',
                            timestamp=datetime.utcnow() - timedelta(minutes=4)),
                ChatMessage(session_id=session_id, role='assistant',
                            content='Слышу, звучит утомительно. Рутина выматывает. А было что-то, что наоборот, порадовало?',
                            timestamp=datetime.utcnow() - timedelta(minutes=3)),
                ChatMessage(session_id=session_id, role='user',
                            content='Да, удалось закрыть старый баг, который всех бесил.',
                            timestamp=datetime.utcnow() - timedelta(minutes=2)),
            ]
            session.add_all(messages)
            await session.commit()
            logger.info(f"Для сотрудника {emp_id} создана сессия {session_id} с {len(messages)} сообщениями.")

            logger.info("Создание мокового анализа...")
            analysis = DialogueAnalysis(
                session_id=session_id,
                sentiment=-0.2 + idx * 0.1,
                is_burnout_risk_detected=bool(idx % 2)
            )
            session.add(analysis)
            await session.commit()
            logger.info(f"Анализ для сессии {session_id} сохранен.")

        logger.info("Создание моковых записей BurnoutPrediction...")
        for idx, emp in enumerate(MOCK_EMPLOYEES):
            prediction = BurnoutPrediction(
                user_id=emp['id'],
                topics_from_dialogues=MOCK_TOPICS[idx],
                probability_of_burnout=0.3 + idx * 0.3,
                shap_explanations=MOCK_SHAP
            )
            session.add(prediction)
        await session.commit()
        logger.info(f"{len(MOCK_EMPLOYEES)} записей BurnoutPrediction добавлено.")

    await engine.dispose()
    logger.info("БД заполнена")


if __name__ == "__main__":
    asyncio.run(seed_database())
