import { request } from './client';

export async function fetchGeneratorSchemas() {
  try {
    const payload = await request('/api/v1/generate-data/schemas');
    return payload?.schemas && typeof payload.schemas === 'object' ? payload.schemas : {};
  } catch {
    return {};
  }
}

export async function generateSyntheticCsv(payload) {
  const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
  const API_KEY = import.meta.env.VITE_API_KEY;
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (API_KEY) headers['x-api-key'] = API_KEY;
    const response = await fetch(`${API_BASE}/api/v1/generate-data`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    const blob = await response.blob();
    const text = await blob.text();
    return { blob, text };
  } catch {
    return null;
  }
}

export async function generateSyntheticAndSave(payload) {
  try {
    return await request('/api/v1/generate-data/save', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch {
    return null;
  }
}

export async function fetchModelInfo() {
  try {
    return await request('/api/v1/ml/info');
  } catch {
    return null;
  }
}

export async function trainModel(payload) {
  try {
    return await request('/api/v1/ml/train', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch {
    return null;
  }
}

export async function trainModelInlineCsv(csvContent, targetRecall = 0.7, sourceName = 'uploaded_training.csv') {
  try {
    return await request('/api/v1/ml/train-inline', {
      method: 'POST',
      body: JSON.stringify({ csv_content: csvContent, target_recall: targetRecall, source_name: sourceName }),
    });
  } catch {
    return null;
  }
}
