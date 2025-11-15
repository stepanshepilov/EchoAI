from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    name = Column(String, nullable=True) 
    cdek_id = Column(String, nullable=True, unique=True)
    features = relationship(
        "EmployeeFeatures",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="desc(EmployeeFeatures.created_at)"
    )
    # Здесь будут другие поля, которые мы получим от организаторов

    dialogue_sessions = relationship("DialogueSession", back_populates="employee", cascade="all, delete-orphan")

    # survey_result = relationship(
    #     "SurveyResult",
    #     back_populates="employee",
    #     uselist=False,
    #     cascade="all, delete-orphan"
    # )

    # burnout_predictions = relationship(
    #     "BurnoutPrediction",
    #     back_populates="employee",
    #     cascade="all, delete-orphan"
    # )

    def __repr__(self):
        return f"<Employee(id={self.id}, telegram_id={self.telegram_id})>"

class DialogueSession(Base):
    __tablename__ = 'dialogue_sessions'
    id = Column(String, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Employee", back_populates="dialogue_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    analysis = relationship("DialogueAnalysis", back_populates="session", uselist=False, cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True)
    session_id = Column(String, ForeignKey('dialogue_sessions.id'))
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

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
    user_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)
    topics_from_dialogues = Column(JSON, nullable=False)
    probability_of_burnout = Column(Float, nullable=False)
    shap_explanations = Column(JSON, nullable=False)


    employee = relationship("Employee", backref="burnout_predictions")


class SurveyResult(Base):
    __tablename__ = "survey_results"

    id = Column(Integer, primary_key=True)

    # связь с сотрудником
    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
        unique=True, 
        index=True
    )

    q1  = Column(String, nullable=True)
    q2  = Column(String, nullable=True)
    q3  = Column(String, nullable=True)
    q4  = Column(String, nullable=True)
    q5  = Column(String, nullable=True)
    q6  = Column(String, nullable=True)
    q7  = Column(String, nullable=True)
    q8  = Column(String, nullable=True)
    q9  = Column(String, nullable=True)
    q10 = Column(String, nullable=True)
    q11 = Column(String, nullable=True)
    q12 = Column(String, nullable=True)
    q13 = Column(String, nullable=True)
    q14 = Column(String, nullable=True)
    q15 = Column(String, nullable=True)
    q16 = Column(String, nullable=True)
    q17 = Column(String, nullable=True)
    q18 = Column(String, nullable=True)
    q19 = Column(String, nullable=True)
    q20 = Column(String, nullable=True)
    q21 = Column(String, nullable=True)
    q22 = Column(String, nullable=True)


class EmployeeFeatures(Base):
    __tablename__ = 'employee_features'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    age = Column(Integer)
    gender = Column(Integer)
    tenure_months = Column(Integer)

    tasks_completed_last_30d = Column(Integer)
    tasks_failed_last_30d = Column(Integer)
    tasks_completed_last_90d = Column(Integer)
    tasks_failed_last_90d = Column(Integer)
    tasks_completed_last_365d = Column(Integer)
    tasks_failed_last_365d = Column(Integer)

    sick_leave_count_last_30d = Column(Integer)
    short_sick_leaves_count_last_30d = Column(Integer)
    total_sick_days_last_30d = Column(Integer)
    sick_leave_count_last_90d = Column(Integer)
    short_sick_leaves_count_last_90d = Column(Integer)
    total_sick_days_last_90d = Column(Integer)
    sick_leave_count_last_365d = Column(Integer)
    short_sick_leaves_count_last_365d = Column(Integer)
    total_sick_days_last_365d = Column(Integer)
    days_since_last_vacation = Column(Integer)

    avg_sentiment_last_30d = Column(Float)
    avg_sentiment_last_90d = Column(Float)
    avg_sentiment_last_365d = Column(Float)
    sentiment_trend_last_90d = Column(Float)

    employee = relationship("Employee", back_populates="features")