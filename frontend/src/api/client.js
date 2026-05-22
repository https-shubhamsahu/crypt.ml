const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const API_KEY = import.meta.env.VITE_API_KEY;

function buildHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra };
  if (API_KEY) {
    headers['x-api-key'] = API_KEY;
  }
  return headers;
}

export async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = buildHeaders(options.headers);
  const response = await fetch(url, { ...options, headers });
  
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error: ${response.status}`);
  }
  
  return response.json();
}
