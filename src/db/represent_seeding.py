import asyncio
import os
import uuid
import logging
import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy import (Column, Integer, String, Float, DateTime,
                        JSON, Boolean, ForeignKey)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# --- 1. Определение моделей SQLAlchemy (без изменений) ---

Base = declarative_base()


class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    name = Column(String, nullable=True)
    cdek_id = Column(String, nullable=True, unique=True)
    features = relationship("EmployeeFeatures", back_populates="employee", cascade="all, delete-orphan", uselist=False)
    dialogue_sessions = relationship("DialogueSession", back_populates="employee", cascade="all, delete-orphan")
    survey_result = relationship("SurveyResult", back_populates="employee", cascade="all, delete-orphan", uselist=False)
    burnout_prediction = relationship("BurnoutPrediction", back_populates="employee", cascade="all, delete-orphan",
                                      uselist=False)


class DialogueSession(Base):
    __tablename__ = 'dialogue_sessions'
    id = Column(String, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    employee = relationship("Employee", back_populates="dialogue_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    analysis = relationship("DialogueAnalysis", back_populates="session", uselist=False, cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True)
    session_id = Column(String, ForeignKey('dialogue_sessions.id'))
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session = relationship("DialogueSession", back_populates="messages")


class DialogueAnalysis(Base):
    __tablename__ = 'dialogue_analysis'
    id = Column(Integer, primary_key=True)
    session_id = Column(String, ForeignKey('dialogue_sessions.id'), unique=True)
    sentiment = Column(Float)
    is_burnout_risk_detected = Column(Boolean)
    comment = Column(String, nullable=True)
    session = relationship("DialogueSession", back_populates="analysis")


class BurnoutPrediction(Base):
    __tablename__ = 'burnout_predictions'
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, unique=True, index=True)
    topics_from_dialogues = Column(JSON, nullable=False)
    probability_of_burnout = Column(Float, nullable=False)
    shap_explanations = Column(JSON, nullable=False)
    employee = relationship("Employee", back_populates="burnout_prediction")


class SurveyResult(Base):
    __tablename__ = "survey_results"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, unique=True, index=True)
    q1 = Column(String, nullable=True);
    q2 = Column(String, nullable=True);
    q3 = Column(String, nullable=True)
    q4 = Column(String, nullable=True);
    q5 = Column(String, nullable=True);
    q6 = Column(String, nullable=True)
    q7 = Column(String, nullable=True);
    q8 = Column(String, nullable=True);
    q9 = Column(String, nullable=True)
    q10 = Column(String, nullable=True);
    q11 = Column(String, nullable=True);
    q12 = Column(String, nullable=True)
    q13 = Column(String, nullable=True);
    q14 = Column(String, nullable=True);
    q15 = Column(String, nullable=True)
    q16 = Column(String, nullable=True);
    q17 = Column(String, nullable=True);
    q18 = Column(String, nullable=True)
    q19 = Column(String, nullable=True);
    q20 = Column(String, nullable=True);
    q21 = Column(String, nullable=True)
    q22 = Column(String, nullable=True)
    employee = relationship("Employee", back_populates="survey_result")


class EmployeeFeatures(Base):
    __tablename__ = 'employee_features'
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    age = Column(Integer);
    gender = Column(Integer);
    tenure_months = Column(Integer)
    tasks_completed_last_30d = Column(Integer);
    tasks_failed_last_30d = Column(Integer)
    tasks_completed_last_90d = Column(Integer);
    tasks_failed_last_90d = Column(Integer)
    tasks_completed_last_365d = Column(Integer);
    tasks_failed_last_365d = Column(Integer)
    sick_leave_count_last_30d = Column(Integer);
    short_sick_leaves_count_last_30d = Column(Integer)
    total_sick_days_last_30d = Column(Integer);
    sick_leave_count_last_90d = Column(Integer)
    short_sick_leaves_count_last_90d = Column(Integer);
    total_sick_days_last_90d = Column(Integer)
    sick_leave_count_last_365d = Column(Integer);
    short_sick_leaves_count_last_365d = Column(Integer)
    total_sick_days_last_365d = Column(Integer);
    days_since_last_vacation = Column(Integer)
    avg_sentiment_last_30d = Column(Float);
    avg_sentiment_last_90d = Column(Float)
    avg_sentiment_last_365d = Column(Float);
    sentiment_trend_last_90d = Column(Float)
    employee = relationship("Employee", back_populates="features")


# --- 2. Настройки и инициализация ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
DB_FILE = "./database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"
fake = Faker('ru_RU')

# --- 3. Шаблоны для генерации моковых данных ---
MOCK_SURVEY_ANSWERS = ['Никогда', 'Почти никогда', 'Редко', 'Иногда', 'Часто', 'Очень часто']
MOCK_TOPICS_TEMPLATE = [
    {"topic": "Переработки", "category": "workload"}, {"topic": "Конфликт с коллегой", "category": "team_relations"},
    {"topic": "Недостаток признания", "category": "recognition"}, {"topic": "Усталость", "category": "health"},
    {"topic": "Выгорание", "category": "burnout"}, {"topic": "Сложная задача", "category": "tasks"},
]


# --- 4. Основная функция для заполнения БД ---
async def seed_representative_data():
    """Генерирует 20 репрезентативных записей для всех таблиц."""
    if os.path.exists(DB_FILE):
        logger.info(f"Удаление старой базы данных: {DB_FILE}")
        os.remove(DB_FILE)

    engine = create_async_engine(DATABASE_URL)

    logger.info("Создание таблиц в базе данных...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы успешно созданы.")

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        logger.info("Генерация 20 репрезентативных записей...")

        for i in range(1, 21):
            employee_id = i

            # 1. Создаем сотрудника (Employee)
            new_employee = Employee(
                id=employee_id,
                telegram_id=100000000 + employee_id,  # Гарантированно уникальный ID
                name=fake.name(),
                cdek_id=str(uuid.uuid4())[:8].upper()
            )
            session.add(new_employee)

            # 2. Генерируем фичи для сотрудника (EmployeeFeatures)
            new_features = EmployeeFeatures(
                employee_id=employee_id,
                age=random.randint(22, 58),
                gender=random.choice([0, 1]),
                tenure_months=random.randint(1, 72),
                tasks_completed_last_30d=random.randint(10, 100),
                tasks_failed_last_30d=random.randint(0, 5),
                tasks_completed_last_90d=random.randint(40, 300),
                tasks_failed_last_90d=random.randint(2, 15),
                tasks_completed_last_365d=random.randint(200, 1200),
                tasks_failed_last_365d=random.randint(10, 60),
                sick_leave_count_last_30d=random.choice([0, 0, 0, 1, 2]),
                short_sick_leaves_count_last_30d=random.choice([0, 0, 1]),
                total_sick_days_last_30d=random.choice([0, 0, 0, 1, 2, 3, 5]),
                sick_leave_count_last_90d=random.randint(0, 4),
                short_sick_leaves_count_last_90d=random.randint(0, 3),
                total_sick_days_last_90d=random.randint(0, 10),
                sick_leave_count_last_365d=random.randint(1, 8),
                short_sick_leaves_count_last_365d=random.randint(1, 6),
                total_sick_days_last_365d=random.randint(2, 25),
                days_since_last_vacation=random.randint(20, 400),
                avg_sentiment_last_30d=round(random.uniform(-0.8, 0.8), 2),
                avg_sentiment_last_90d=round(random.uniform(-0.6, 0.6), 2),
                avg_sentiment_last_365d=round(random.uniform(-0.5, 0.7), 2),
                sentiment_trend_last_90d=round(random.uniform(-0.3, 0.3), 2)
            )
            session.add(new_features)

            # 3. Генерируем результат опроса (SurveyResult)
            survey = SurveyResult(
                employee_id=employee_id,
                **{f'q{j}': random.choice(MOCK_SURVEY_ANSWERS) for j in range(1, 23)}
            )
            session.add(survey)

            # 4. Генерируем сессию диалога, сообщения и анализ (DialogueSession, ChatMessage, DialogueAnalysis)
            session_id = str(uuid.uuid4())
            new_session = DialogueSession(id=session_id, employee_id=employee_id)
            now_utc = datetime.now(timezone.utc)
            messages = [
                ChatMessage(session_id=session_id, role='assistant', content=fake.sentence(),
                            timestamp=now_utc - timedelta(minutes=random.randint(5, 10))),
                ChatMessage(session_id=session_id, role='user', content=fake.sentence(),
                            timestamp=now_utc - timedelta(minutes=random.randint(1, 4))),
            ]
            analysis = DialogueAnalysis(
                session_id=session_id,
                sentiment=round(random.uniform(-1.0, 1.0), 2),
                is_burnout_risk_detected=random.choice([True, False, False]),  # Смещаем в сторону False для реализма
                comment=fake.paragraph(nb_sentences=2)
            )
            session.add(new_session)
            session.add_all(messages)
            session.add(analysis)

            # 5. Генерируем предсказание выгорания (BurnoutPrediction)
            burnout_prob = round(random.uniform(0.05, 0.95), 2)
            num_topics = random.randint(1, 3)
            topics = random.sample(MOCK_TOPICS_TEMPLATE, num_topics)
            for topic in topics:
                topic.update({
                    "mentions": random.randint(1, 5), "sentiment": round(random.uniform(-1.0, 0.2), 2),
                    "importance": round(random.random(), 2),
                    "examples": [fake.sentence() for _ in range(random.randint(1, 2))]
                })

            prediction = BurnoutPrediction(
                employee_id=employee_id,
                topics_from_dialogues=topics,
                probability_of_burnout=burnout_prob,
                shap_explanations={"base_value": 0.35, "prediction_value": burnout_prob, "features": []}
            )
            session.add(prediction)

        await session.commit()
        logger.info("Данные успешно сгенерированы и добавлены в БД.")

    await engine.dispose()
    logger.info("Соединение с БД закрыто.")


if __name__ == "__main__":
    asyncio.run(seed_representative_data())