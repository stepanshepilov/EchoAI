from pydantic import BaseModel
from typing import List, Dict, Any


class EmployeePulse(BaseModel):
    telegram_id: str
    risk_probability: float
    sentiment_trend: float


class TeamPulseResponse(BaseModel):
    overall_risk_score: float
    risk_dynamics_weekly: str
    distribution: Dict[str, int]
    employees: List[EmployeePulse]


class ShapFactor(BaseModel):
    feature: str
    value: Any
    contribution: float


class ExplanationResponse(BaseModel):
    telegram_id: str
    burnout_probability: float
    shap_explanation: Dict[str, Any]


class ChatMessage(BaseModel):
    role: str  # "user" или "assistant"
    content: str


class ChatRequest(BaseModel):
    history: List[ChatMessage]


class ChatResponse(BaseModel):
    response: str
