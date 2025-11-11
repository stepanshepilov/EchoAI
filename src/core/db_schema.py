from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class Employee(Base):
    __tablename__ = 'employees'
    id = Column(Integer, primary_key=True)
    # здесь будут поля из данных организаторов
    
    dialogue_sessions = relationship("DialogueSession", back_populates="employee")

class DialogueSession(Base):
    __tablename__ = 'dialogue_sessions'
    id = Column(String, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Employee", back_populates="dialogue_sessions")
    messages = relationship("ChatMessage", back_populates="session")
    analysis = relationship("DialogueAnalysis", back_populates="session", uselist=False)

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
    topics = Column(JSON)
    is_burnout_risk_detected = Column(Boolean)
    summary = Column(String)
    
    session = relationship("DialogueSession", back_populates="analysis")
