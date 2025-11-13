from pydantic import BaseModel
from typing import List, Dict, Any

class EmployeePulse(BaseModel):
    token: str
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
    token: str
    burnout_probability: float
    shap_explanation: Dict[str, Any]