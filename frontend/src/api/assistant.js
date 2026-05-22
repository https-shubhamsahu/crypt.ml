import { request } from './client';

export async function fetchSessionRules(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  try {
    const payload = await request(`/api/v1/session-rules${suffix}`);
    return Array.isArray(payload?.rules) ? payload.rules : [];
  } catch {
    return [];
  }
}

export async function createSessionRule(text, datasetId = null) {
  const value = String(text || '').trim();
  if (!value) return null;
  try {
    return await request('/api/v1/session-rules', {
      method: 'POST',
      body: JSON.stringify({ text: value, dataset_id: datasetId }),
    });
  } catch {
    return null;
  }
}

export async function clearSessionRules(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  try {
    return await request(`/api/v1/session-rules${suffix}`, {
      method: 'DELETE',
    });
  } catch {
    return null;
  }
}

export async function fetchAssistantHistory(datasetId = null, limit = 80) {
  const queryParts = [`limit=${encodeURIComponent(limit)}`];
  if (datasetId) {
    queryParts.push(`dataset_id=${encodeURIComponent(datasetId)}`);
  }
  try {
    const payload = await request(`/api/v1/llm/chat-history?${queryParts.join('&')}`);
    return Array.isArray(payload?.messages) ? payload.messages : [];
  } catch {
    return [];
  }
}

export async function clearAssistantHistory(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  try {
    return await request(`/api/v1/llm/chat-history${suffix}`, {
      method: 'DELETE',
    });
  } catch {
    return null;
  }
}

export async function sendAssistantMessage(message, includeMlArtifacts = true, datasetId = null, storeInHistory = true) {
  const value = String(message || '').trim();
  if (!value) return null;
  try {
    return await request('/api/v1/llm/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: value,
        include_ml_artifacts: includeMlArtifacts,
        dataset_id: datasetId,
        store_in_history: storeInHistory,
      }),
    });
  } catch {
    return null;
  }
}
