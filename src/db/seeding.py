import asyncio
import os
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine
from ..settings import settings
from .models import Base, Employee, DialogueSession, ChatMessage, DialogueAnalysis

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MOCK_EMPLOYEES = [
    {"id": 1, "telegram_id": 111111111},
    {"id": 2, "telegram_id": 222222222},
    {"id": 3, "telegram_id": 333333333},
]

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
    
    # Создаем сессию для записи данных
    from .session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        logger.info("Добавление моковых сотрудников...")
        for emp_data in MOCK_EMPLOYEES:
            employee = Employee(**emp_data)
            session.add(employee)
        await session.commit()
        logger.info(f"{len(MOCK_EMPLOYEES)} сотрудников добавлено.")
        
        logger.info("Создание моковой истории диалога...")
        
        emp1_id = MOCK_EMPLOYEES[0]['id']
        session_id = str(uuid.uuid4())
        new_session = DialogueSession(id=session_id, employee_id=emp1_id)
        session.add(new_session)
        
        messages = [
            ChatMessage(session_id=session_id, role='assistant', content='Привет! Это Эхо. Как прошла неделя?', timestamp=datetime.utcnow() - timedelta(minutes=5)),
            ChatMessage(session_id=session_id, role='user', content='Привет. Неделя была тяжелая, много отчетов.', timestamp=datetime.utcnow() - timedelta(minutes=4)),
            ChatMessage(session_id=session_id, role='assistant', content='Слышу, звучит утомительно. Рутина выматывает. А было что-то, что наоборот, порадовало?', timestamp=datetime.utcnow() - timedelta(minutes=3)),
            ChatMessage(session_id=session_id, role='user', content='Да, удалось закрыть старый баг, который всех бесил.', timestamp=datetime.utcnow() - timedelta(minutes=2)),
        ]
        session.add_all(messages)
        await session.commit()
        logger.info(f"Для сотрудника {emp1_id} создана сессия {session_id} с {len(messages)} сообщениями.")

        logger.info("Создание мокового анализа...")
        analysis = DialogueAnalysis(
            session_id=session_id,
            sentiment=-0.2,
            is_burnout_risk_detected=True
        )
        session.add(analysis)
        await session.commit()
        logger.info(f"Анализ для сессии {session_id} сохранен.")
        
    await engine.dispose()
    logger.info("БД заполнена")

if __name__ == "__main__":
    asyncio.run(seed_database())
