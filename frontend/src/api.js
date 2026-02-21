const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const API_KEY = import.meta.env.VITE_API_KEY

function buildHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra }
  if (API_KEY) {
    headers['x-api-key'] = API_KEY
  }
  return headers
}

const mockDatasets = [
  {
    dataset_id: 'mock_1',
    name: 'Q3 Transaction Batch A',
    upload_date: '2023-10-24T00:00:00Z',
    total_rows: 14500,
    total_columns: 12,
    human_size: '8.1 MB',
    risk_level: 'Unknown',
    status: 'In Progress',
    fraud_pct: 'Calculating',
  },
  {
    dataset_id: 'mock_2',
    name: 'Q2 Transaction Batch B',
    upload_date: '2023-07-12T00:00:00Z',
    total_rows: 52102,
    total_columns: 12,
    human_size: '22.5 MB',
    risk_level: 'Low',
    status: 'Completed',
    fraud_pct: '1.1%',
  },
  {
    dataset_id: 'mock_3',
    name: 'SWIFT Transfers - High Value',
    upload_date: '2023-06-01T00:00:00Z',
    total_rows: 4200,
    total_columns: 12,
    human_size: '3.8 MB',
    risk_level: 'High',
    status: 'Completed',
    fraud_pct: '12.7%',
  },
]

export async function fetchDatasets() {
  try {
    const response = await fetch(`${API_BASE}/api/v1/datasets`, {
      method: 'GET',
      headers: buildHeaders(),
    })

    if (!response.ok) {
      return mockDatasets
    }

    const payload = await response.json()
    if (Array.isArray(payload)) {
      return payload
    }
    if (Array.isArray(payload?.items)) {
      return payload.items
    }
    return mockDatasets
  } catch {
    return mockDatasets
  }
}

export async function fetchDatasetSummary(datasetId) {
  if (!datasetId) return null
  try {
    const response = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/summary`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchDatasetTransactions(datasetId, limit = 25) {
  if (!datasetId) return []
  try {
    const response = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/transactions?limit=${limit}`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return []
    const payload = await response.json()
    return Array.isArray(payload?.items) ? payload.items : []
  } catch {
    return []
  }
}

export async function fetchDatasetAnalytics(datasetId, days = 30) {
  if (!datasetId) return null
  try {
    const response = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/analytics?days=${days}`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchSessionRules(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ''
  try {
    const response = await fetch(`${API_BASE}/api/v1/session-rules${suffix}`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return []
    const payload = await response.json()
    return Array.isArray(payload?.rules) ? payload.rules : []
  } catch {
    return []
  }
}

export async function createSessionRule(text, datasetId = null) {
  const value = String(text || '').trim()
  if (!value) return null

  try {
    const response = await fetch(`${API_BASE}/api/v1/session-rules`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ text: value, dataset_id: datasetId }),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function clearSessionRules(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ''
  try {
    const response = await fetch(`${API_BASE}/api/v1/session-rules${suffix}`, {
      method: 'DELETE',
      headers: buildHeaders(),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchAssistantHistory(datasetId = null, limit = 80) {
  const queryParts = [`limit=${encodeURIComponent(limit)}`]
  if (datasetId) {
    queryParts.push(`dataset_id=${encodeURIComponent(datasetId)}`)
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/llm/chat-history?${queryParts.join('&')}`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return []
    const payload = await response.json()
    return Array.isArray(payload?.messages) ? payload.messages : []
  } catch {
    return []
  }
}

export async function clearAssistantHistory(datasetId = null) {
  const suffix = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : ''
  try {
    const response = await fetch(`${API_BASE}/api/v1/llm/chat-history${suffix}`, {
      method: 'DELETE',
      headers: buildHeaders(),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function sendAssistantMessage(message, includeMlArtifacts = true, datasetId = null, storeInHistory = true) {
  const value = String(message || '').trim()
  if (!value) return null

  try {
    const response = await fetch(`${API_BASE}/api/v1/llm/chat`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({
        message: value,
        include_ml_artifacts: includeMlArtifacts,
        dataset_id: datasetId,
        store_in_history: storeInHistory,
      }),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchGeneratorSchemas() {
  try {
    const response = await fetch(`${API_BASE}/api/v1/generate-data/schemas`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return {}
    const payload = await response.json()
    return payload?.schemas && typeof payload.schemas === 'object' ? payload.schemas : {}
  } catch {
    return {}
  }
}

export async function generateSyntheticCsv(payload) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/generate-data`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    })
    if (!response.ok) return null
    const blob = await response.blob()
    const text = await blob.text()
    return { blob, text }
  } catch {
    return null
  }
}

export async function generateSyntheticAndSave(payload) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/generate-data/save`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function fetchModelInfo() {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ml/info`, {
      method: 'GET',
      headers: buildHeaders(),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function trainModel(payload) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ml/train`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify(payload),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

export async function trainModelInlineCsv(csvContent, targetRecall = 0.7, sourceName = 'uploaded_training.csv') {
  try {
    const response = await fetch(`${API_BASE}/api/v1/ml/train-inline`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({ csv_content: csvContent, target_recall: targetRecall, source_name: sourceName }),
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}
