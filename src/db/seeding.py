import asyncio
import os
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine
from src.settings import settings
from src.db.models import Base, Employee, DialogueSession, ChatMessage, DialogueAnalysis, BurnoutPrediction, SurveyResult, EmployeeFeatures
from faker import Faker
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fake = Faker('ru_RU')

MOCK_EMPLOYEES = [
    {"id": i, "telegram_id": 111111110 + i, 'name': f'Сотрудник {i}', 'cdek_id': str(122 + i)}
    for i in range(1, 21)
]

MOCK_FEATURES = []
for i in range(1, 21):
    tenure = random.randint(3, 120)
    features = {
        'employee_id': i, 'age': random.randint(22, 60), 'gender': random.choice([0, 1]), 'tenure_months': tenure,
        'tasks_completed_last_30d': random.randint(20, 100), 'tasks_failed_last_30d': random.randint(0, 10),
        'tasks_completed_last_90d': random.randint(60, 300), 'tasks_failed_last_90d': random.randint(1, 30),
        'tasks_completed_last_365d': random.randint(240, 1200), 'tasks_failed_last_365d': random.randint(5, 120),
        'sick_leave_count_last_30d': random.randint(0, 2), 'short_sick_leaves_count_last_30d': random.randint(0, 2),
        'total_sick_days_last_30d': random.randint(0, 5),
        'sick_leave_count_last_90d': random.randint(0, 5), 'short_sick_leaves_count_last_90d': random.randint(0, 5),
        'total_sick_days_last_90d': random.randint(0, 15),
        'sick_leave_count_last_365d': random.randint(0, 15), 'short_sick_leaves_count_last_365d': random.randint(0, 10),
        'total_sick_days_last_365d': random.randint(0, 40),
        'days_since_last_vacation': random.randint(10, 400),
        'avg_sentiment_last_30d': round(random.uniform(-0.8, 0.8), 2),
        'avg_sentiment_last_90d': round(random.uniform(-0.7, 0.7), 2),
        'avg_sentiment_last_365d': round(random.uniform(-0.5, 0.5), 2),
        'sentiment_trend_last_90d': round(random.uniform(-0.3, 0.3), 2)
    }
    MOCK_FEATURES.append(features)


SURVEY_ANSWERS = {f'q{i}': random.choice(['Никогда', 'Редко', 'Иногда', 'Часто', 'Очень часто']) for i in range(1, 23)}
MOCK_SURVEYS = []
for i in range(1, 21):
    answers = SURVEY_ANSWERS.copy()
    # Вносим немного разнообразия в ответы
    for _ in range(5):
        q_key = f'q{random.randint(1, 22)}'
        answers[q_key] = random.choice(['Никогда', 'Редко', 'Иногда', 'Часто', 'Очень часто'])
    survey = {'employee_id': i, **answers}
    MOCK_SURVEYS.append(survey)


MOCK_TOPICS_POOL = [
    {"topic": "Переработки", "category": "workload", "sentiment": -0.6, "importance": 0.8, "examples": ["работаю по выходным", "засиживаюсь допоздна"]},
    {"topic": "Конфликт с коллегой", "category": "team_relations", "sentiment": -0.8, "importance": 0.6, "examples": ["постоянные споры", "не находим общий язык"]},
    {"topic": "Недостаток признания", "category": "recognition", "sentiment": -0.3, "importance": 0.5, "examples": ["никто не замечает мои усилия"]},
    {"topic": "Усталость", "category": "health", "sentiment": -0.7, "importance": 0.7, "examples": ["чувствую себя выжатым"]},
    {"topic": "Сложные задачи", "category": "workload", "sentiment": 0.2, "importance": 0.4, "examples": ["интересный проект", "развиваюсь"]},
    {"topic": "Хороший коллектив", "category": "team_relations", "sentiment": 0.9, "importance": 0.9, "examples": ["всегда помогут", "приятно общаться"]},
    {"topic": "Премия", "category": "recognition", "sentiment": 0.9, "importance": 0.8, "examples": ["получил бонус", "оценили мою работу"]},
    {"topic": "Проблемы со здоровьем", "category": "health", "sentiment": -0.9, "importance": 0.9, "examples": ["часто болею", "постоянно что-то болит"]},
]

MOCK_TOPICS = []
for _ in range(20):
    num_topics = random.randint(1, 4)
    topics = random.sample(MOCK_TOPICS_POOL, num_topics)
    for topic in topics:
        topic['mentions'] = random.randint(1, 5)
    MOCK_TOPICS.append(topics)


MOCK_SHAP = {
    "base_value": 0.35,
    "prediction_value": round(random.uniform(0.1, 0.95), 2),
    "features": [
        {
            "feature_name": "days_since_last_vacation",
            "feature_value": random.randint(10, 400),
            "shap_value": round(random.uniform(-0.3, 0.3), 2),
            "display_value": f"{random.randint(10, 400)} дней",
            "category": "time_off"
        },
        {
            "feature_name": "avg_sentiment_last_30d",
            "feature_value": round(random.uniform(-0.8, 0.8), 2),
            "shap_value": round(random.uniform(-0.3, 0.3), 2),
            "display_value": f"{int(round(random.uniform(-0.8, 0.8), 2) * 100)}%",
            "category": "sentiment"
        },
        {
            "feature_name": "tasks_failed_last_90d",
            "feature_value": random.randint(1, 30),
            "shap_value": round(random.uniform(-0.2, 0.2), 2),
            "display_value": f"{random.randint(1, 30)} шт.",
            "category": "performance"
        }
    ],
    "top_risk_factors": ["days_since_last_vacation", "avg_sentiment_last_30d"],
    "top_protective_factors": ["tenure_months"]
}


async def seed_database():
    db_file = settings.DATABASE_URL.split('///')[-1]
    print(db_file)

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

        logger.info("Добавление моковых фичей сотрудников...")
        for features_data in MOCK_FEATURES:
            features = EmployeeFeatures(**features_data)
            session.add(features)
        await session.commit()
        logger.info(f"{len(MOCK_FEATURES)} записей с фичами добавлено.")

        logger.info("Добавление моковых результатов опросов...")
        for survey_data in MOCK_SURVEYS:
            survey = SurveyResult(**survey_data)
            session.add(survey)
        await session.commit()
        logger.info(f"{len(MOCK_SURVEYS)} результатов опросов добавлено.")

        logger.info("Создание моковой истории диалога...")
        for idx, emp in enumerate(MOCK_EMPLOYEES):
            emp_id = emp['id']
            session_id = str(uuid.uuid4())
            new_session = DialogueSession(id=session_id, employee_id=emp_id)
            session.add(new_session)

            messages = [
                ChatMessage(session_id=session_id, role='assistant', content='Привет! Это Эхо. Как прошла неделя?',
                            timestamp=datetime.utcnow() - timedelta(days=7, minutes=5)),
                ChatMessage(session_id=session_id, role='user', content=fake.sentence(nb_words=10),
                            timestamp=datetime.utcnow() - timedelta(days=7, minutes=4)),
                ChatMessage(session_id=session_id, role='assistant',
                            content='Слышу, звучит утомительно. Рутина выматывает. А было что-то, что наоборот, порадовало?',
                            timestamp=datetime.utcnow() - timedelta(days=7, minutes=3)),
                ChatMessage(session_id=session_id, role='user',
                            content=fake.sentence(nb_words=8),
                            timestamp=datetime.utcnow() - timedelta(days=7, minutes=2)),
            ]
            session.add_all(messages)
            await session.commit()
            logger.info(f"Для сотрудника {emp_id} создана сессия {session_id} с {len(messages)} сообщениями.")

            logger.info("Создание мокового анализа...")
            analysis = DialogueAnalysis(
                session_id=session_id,
                sentiment=round(random.uniform(-1, 1), 2),
                is_burnout_risk_detected=bool(random.getrandbits(1))
            )
            session.add(analysis)
            await session.commit()
            logger.info(f"Анализ для сессии {session_id} сохранен.")

        logger.info("Создание моковых записей BurnoutPrediction...")
        for idx, emp in enumerate(MOCK_EMPLOYEES):
            # Генерируем новый MOCK_SHAP для каждой записи
            current_shap = {
                "base_value": 0.35,
                "prediction_value": round(random.uniform(0.1, 0.95), 2),
                "features": [
                    {
                        "feature_name": "days_since_last_vacation",
                        "feature_value": random.randint(10, 400),
                        "shap_value": round(random.uniform(-0.3, 0.3), 2),
                        "display_value": f"{random.randint(10, 400)} дней",
                        "category": "time_off"
                    },
                    {
                        "feature_name": "avg_sentiment_last_30d",
                        "feature_value": round(random.uniform(-0.8, 0.8), 2),
                        "shap_value": round(random.uniform(-0.3, 0.3), 2),
                        "display_value": f"{int(round(random.uniform(-0.8, 0.8), 2) * 100)}%",
                        "category": "sentiment"
                    },
                    {
                        "feature_name": "tasks_failed_last_90d",
                        "feature_value": random.randint(1, 30),
                        "shap_value": round(random.uniform(-0.2, 0.2), 2),
                        "display_value": f"{random.randint(1, 30)} шт.",
                        "category": "performance"
                    }
                ],
                "top_risk_factors": random.sample(["days_since_last_vacation", "avg_sentiment_last_30d", "tasks_failed_last_90d"], 2),
                "top_protective_factors": random.sample(["tenure_months", "tasks_completed_last_30d"], 1)
            }
            prediction = BurnoutPrediction(
                user_id=emp['id'],
                topics_from_dialogues=MOCK_TOPICS[idx],
                probability_of_burnout=round(random.uniform(0.05, 0.95), 2),
                shap_explanations=current_shap
            )
            session.add(prediction)
        await session.commit()
        logger.info(f"{len(MOCK_EMPLOYEES)} записей BurnoutPrediction добавлено.")

    await engine.dispose()
    logger.info("БД заполнена")


if __name__ == "__main__":
    # Для запуска этого скрипта, вам нужно будет создать файлы:
    # src/settings.py
    # src/db/models.py
    # src/db/session.py
    #
    # Примерное содержимое settings.py:
    # class Settings:
    #     DATABASE_URL = "sqlite+aiosqlite:///./test.db"
    # settings = Settings()
    #
    # Примерное содержимое session.py
    # from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    # from sqlalchemy.orm import sessionmaker
    # from src.settings import settings
    #
    # engine = create_async_engine(settings.DATABASE_URL, echo=True)
    # AsyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
    #
    # Вам также нужно будет определить все модели SQLAlchemy в models.py (Base, Employee, и т.д.)
    #
    asyncio.run(seed_database())