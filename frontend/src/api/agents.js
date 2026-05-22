import { request } from './client';

export async function analyzeTransaction(payload) {
  return request('/api/v1/agents/analyze', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export async function fetchDecisions(limit = 50) {
  try {
    return await request(`/api/v1/agents/decisions?limit=${limit}`);
  } catch (error) {
    console.error('Failed to fetch agent decisions:', error);
    return [];
  }
}

export async function fetchRunDetails(runId) {
  return request(`/api/v1/agents/run/${runId}`);
}

export async function fetchTimeline(runId) {
  return request(`/api/v1/agents/timeline/${runId}`);
}

export async function fetchCases(limit = 50) {
  try {
    return await request(`/api/v1/agents/cases?limit=${limit}`);
  } catch (error) {
    console.error('Failed to fetch compliance cases:', error);
    return [];
  }
}

export async function updateCaseStatus(caseId, status) {
  return request(`/api/v1/agents/cases/${caseId}/status`, {
    method: 'POST',
    body: JSON.stringify({ status })
  });
}
