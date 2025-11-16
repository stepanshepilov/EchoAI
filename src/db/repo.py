import uuid
import logging
from abc import ABC, abstractmethod
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update, desc
from src.db.models import Employee, DialogueSession, ChatMessage, DialogueAnalysis, SurveyResult, EmployeeFeatures

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    @abstractmethod
    async def get_or_create_employee(self, telegram_id: int) -> Employee:
        pass

    @abstractmethod
    async def get_employee(self, telegram_id: int) -> Employee:
        pass

    @abstractmethod
    async def create_employee(self, telegram_id: int) -> Employee:
        pass

    @abstractmethod
    async def start_new_session(self, employee_id: int) -> DialogueSession:
        pass

    @abstractmethod
    async def add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        pass

    @abstractmethod
    async def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        pass

    @abstractmethod
    async def save_analysis(self, session_id: str, analysis_data: Dict[str, Any]) -> DialogueAnalysis:
        pass

    @abstractmethod
    async def get_last_session_for_employee(self, employee_id: int) -> Optional[DialogueSession]:
        pass

    @abstractmethod
    async def save_survey_result(self, employee_id: int, answers: Dict[str, str]) -> SurveyResult:
        pass

    @abstractmethod
    async def get_survey_result(self, employee_id: int) -> Optional[SurveyResult]:
        pass


class InMemoryRepository(BaseRepository):
    def __init__(self):
        self._conversations: Dict[str, List[Dict[str, str]]] = {}
        self._analyses: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def start_new_session(self, user_id: int) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {"user_id": user_id}
        self._conversations[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        if session_id in self._conversations:
            self._conversations[session_id].append({"role": role, "content": content})
        else:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Попытка добавить сообщение в несуществующую сессию {session_id}")

    def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        return self._conversations.get(session_id)

    def save_analysis(self, session_id: str, analysis_data: Dict[str, Any]):
        self._analyses[session_id] = analysis_data

    def get_analysis(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._analyses.get(session_id)


class SQLiteRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_employees(self) -> List[Employee]:
        result = await self.session.execute(select(Employee))
        return list(result.scalars().all())

    async def get_or_create_employee(self, telegram_id: int) -> Employee:
        result = await self.session.execute(
            select(Employee).where(Employee.telegram_id == telegram_id)
        )
        employee = result.scalar_one_or_none()

        if not employee:
            logger.info(f"Создание нового сотрудника с telegram_id: {telegram_id}")
            employee = Employee(telegram_id=telegram_id)
            self.session.add(employee)
            await self.session.commit()
            await self.session.refresh(employee)
        return employee

    async def get_employee(self, telegram_id: int, name: str = None, cdek_id: str = None) -> Employee:
        result = await self.session.execute(
            select(Employee).where(Employee.telegram_id == telegram_id)
        )
        employee = result.scalar_one_or_none()
        logger.info(f"Сотрудник  с telegram_id: {telegram_id} найден")
        return employee

    async def create_employee(self, telegram_id: int, name: str = None, cdek_id: str = None) -> Employee:
        logger.info(f"Создание нового сотрудника с telegram_id: {telegram_id}")
        employee = Employee(telegram_id=telegram_id, name=name, cdek_id=cdek_id)
        self.session.add(employee)
        await self.session.commit()
        await self.session.refresh(employee)
        return employee

    async def start_new_session(self, employee_id: int) -> DialogueSession:
        session_id = str(uuid.uuid4())
        new_session = DialogueSession(id=session_id, employee_id=employee_id)
        self.session.add(new_session)
        await self.session.commit()
        await self.session.refresh(new_session)
        logger.info(f"Стартовала новая сессия {session_id} для сотрудника {employee_id}")
        return new_session

    async def add_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        new_message = ChatMessage(session_id=session_id, role=role, content=content)
        self.session.add(new_message)
        await self.session.commit()
        await self.session.refresh(new_message)
        return new_message

    async def get_conversation_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        result = await self.session.execute(
            select(ChatMessage.role, ChatMessage.content)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp)
        )
        history = result.all()
        return [{"role": role, "content": content} for role, content in history] if history else None

    async def save_analysis(self, session_id: str, analysis_data: Dict[str, Any]) -> DialogueAnalysis:

        result = await self.session.execute(
            select(DialogueAnalysis).where(DialogueAnalysis.session_id == session_id)
        )
        existing_analysis = result.scalar_one_or_none()

        comment_data = analysis_data.get('comment')

        if isinstance(comment_data, (list, dict)):
            analysis_data['comment'] = json.dumps(comment_data, ensure_ascii=False)

        if existing_analysis:
            logger.info(f"Обновление анализа для сессии {session_id}")
            stmt = (
                update(DialogueAnalysis)
                .where(DialogueAnalysis.session_id == session_id)
                .values(**analysis_data)
            )
            await self.session.execute(stmt)

            analysis_obj = existing_analysis
        else:
            logger.info(f"Сохранение нового анализа для сессии {session_id}")

            analysis_obj = DialogueAnalysis(session_id=session_id, **analysis_data)
            self.session.add(analysis_obj)

        await self.session.commit()

        await self.session.refresh(analysis_obj)

        return analysis_obj

    async def get_last_session_for_employee(self, employee_id: int) -> Optional[DialogueSession]:
        logger.info(f"Поиск последней сессии для сотрудника с ID: {employee_id}")
        result = await self.session.execute(
            select(DialogueSession)
            .where(DialogueSession.employee_id == employee_id)
            .order_by(desc(DialogueSession.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save_survey_result(self, employee_id: int, answers: Dict[str, str]) -> SurveyResult:
        result = await self.session.execute(
            select(SurveyResult).where(SurveyResult.employee_id == employee_id)
        )
        survey = result.scalar_one_or_none()

        if survey is None:
            survey = SurveyResult(employee_id=employee_id)

        question_fields = [f"q{i}" for i in range(1, 23)]

        for field in question_fields:
            if field in answers:
                setattr(survey, field, answers[field])
            else:
                setattr(survey, field, None)

        self.session.add(survey)
        await self.session.commit()
        await self.session.refresh(survey)
        logger.info(f"Сохранены результаты опроса для сотрудника {employee_id}")
        return survey

    async def get_survey_result(self, employee_id: int) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(
            select(SurveyResult).where(SurveyResult.employee_id == employee_id)
        )
        survey: SurveyResult = result.scalar_one_or_none()

        if survey is None:
            return None

        clean_data = {}

        question_fields = [f"q{i}" for i in range(1, 23)]

        for field in question_fields:
            value = getattr(survey, field)
            if value is not None:
                clean_data[field] = value

        return clean_data

    async def get_latest_features(self, employee_id: int) -> Optional[EmployeeFeatures]:

        logger.info(f"Поиск последнего набора фичей для сотрудника с ID: {employee_id}")
        result = await self.session.execute(
            select(EmployeeFeatures)
            .where(EmployeeFeatures.employee_id == employee_id)
            .order_by(desc(EmployeeFeatures.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_average_sentiment_for_period(self, start_date=None, end_date=None) -> Optional[float]:

        logger.info(f"Расчет среднего sentiment за все время.")
        result = await self.session.execute(
            select(func.avg(DialogueAnalysis.sentiment))
        )
        average_sentiment = result.scalar_one_or_none()
        return average_sentiment

    async def get_all_latest_analysis_comments(self) -> List[str]:

        logger.info("Получение всех последних комментариев анализа для всех сотрудников")

        subquery = (
            select(
                DialogueAnalysis.comment,
                func.row_number()
                .over(
                    partition_by=DialogueSession.employee_id,
                    order_by=desc(DialogueSession.created_at),
                )
                .label("rn"),
            )
            .join(DialogueSession, DialogueAnalysis.session_id == DialogueSession.id)
            .subquery()
        )

        query = select(subquery.c.comment).where(subquery.c.rn == 1)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_active_users(self) -> list[int]:
        stmt = select(Employee.telegram_id).distinct()
        result = await self.session.execute(stmt)
        return result.scalars().all()
