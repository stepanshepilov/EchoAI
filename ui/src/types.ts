export interface Employee {
  token: string;
  name: string;
  risk: number;
}

// GET /dashboard/team-pulse
export interface TeamPulseResponse {
  overall_risk_score: number;
  risk_dynamics_weekly: string;
  distribution: {
    low: number;
    medium: number;
    high: number;
  };
  employees: Array<{
    token: string;
    risk_probability: number;
    sentiment_trend: number;
  }>;
}

// GET /dashboard/employees/{token}/explain
export interface ExplanationResponse {
  token: string;
  burnout_probability: number;
  shap_explanation: {
    base_value: number;
    factors: Array<{
      feature: string;
      value: number | string;
      contribution: number;
    }>;
  };
}

// GET /dashboard/employees/{token}/topics
export interface Topic {
  topic: string;
  category: string;
  mentions: number;
  sentiment: number;
  importance: number;
  examples: string[];
}

export interface TopicsResponse {
  token: string;
  topics: Topic[];
  probability: number;
}