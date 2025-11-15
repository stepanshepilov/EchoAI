import { TeamPulseResponse, ExplanationResponse, TopicsResponse } from '../types';

const API_BASE_URL = 'http://localhost:8000/api/v1';

type WhatIfResult = {
  original_probability: number;
  what_if_vacation_probability: number;
  probability_change: number;
};
type InitialAIResponse = {
  recommendation: string;
};

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

type ChatRequest = {
  history: ChatMessage[];
};

type ChatResponse = {
  response: string;
};

async function apiFetch<T>(url: string): Promise<T> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: "Не удалось прочитать ошибку с сервера" }));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json() as T;
  } catch (error) {
    console.error(`API call failed for GET: ${url}`, error);
    throw error;
  }
}

async function apiPost<T, U>(url: string, body: T): Promise<U> {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: "Не удалось прочитать ошибку с сервера." }));
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    
    return await response.json() as U;
  } catch (error) {
    console.error(`API call failed for POST: ${url}`, error);
    throw error;
  }
}

export const getTeamPulse = (): Promise<TeamPulseResponse> => apiFetch<TeamPulseResponse>(`${API_BASE_URL}/dashboard/team-pulse`);
export const getExplanation = (token: string): Promise<ExplanationResponse> => apiFetch<ExplanationResponse>(`${API_BASE_URL}/dashboard/employees/${token}/explain`);
export const getTopics = (token: string): Promise<TopicsResponse> => apiFetch<TopicsResponse>(`${API_BASE_URL}/dashboard/employees/${token}/topics`);
export const getWhatIfVacation = (token: string): Promise<WhatIfResult> => apiFetch<WhatIfResult>(`${API_BASE_URL}/dashboard/employees/${token}/what-if/vacation`);

export const getInitialAIHelper = (): Promise<InitialAIResponse> => {
  return apiFetch<InitialAIResponse>(`${API_BASE_URL}/llm_helper`);
};

export const postAIChat = (chatHistory: ChatMessage[]): Promise<ChatResponse> => {
  const payload: ChatRequest = {
    history: chatHistory,
  };
  return apiPost<ChatRequest, ChatResponse>(`${API_BASE_URL}/llm_helper/chat`, payload);
};