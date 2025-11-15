import { TeamPulseResponse, ExplanationResponse, TopicsResponse } from '../types';

const API_BASE_URL = 'http://localhost:8000/api/v1';

async function apiFetch<T>(url: string): Promise<T> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json() as T;
  } catch (error) {
    console.error(`API call failed: ${url}`, error);
    throw error;
  }
}

export const getTeamPulse = (): Promise<TeamPulseResponse> => {
  return apiFetch<TeamPulseResponse>(`${API_BASE_URL}/dashboard/team-pulse`);
};

export const getExplanation = (token: string): Promise<ExplanationResponse> => {
  return apiFetch<ExplanationResponse>(`${API_BASE_URL}/dashboard/employees/${token}/explain`);
};

export const getTopics = (token: string): Promise<TopicsResponse> => {
  return apiFetch<TopicsResponse>(`${API_BASE_URL}/dashboard/employees/${token}/topics`);
};