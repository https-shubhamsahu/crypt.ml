import { request } from './client';

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
];

export async function fetchDatasets() {
  try {
    const payload = await request('/api/v1/datasets');
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.items)) return payload.items;
    return mockDatasets;
  } catch {
    return mockDatasets;
  }
}

export async function fetchDatasetSummary(datasetId) {
  if (!datasetId) return null;
  try {
    return await request(`/api/v1/datasets/${datasetId}/summary`);
  } catch {
    return null;
  }
}

export async function fetchDatasetTransactions(datasetId, limit = 25) {
  if (!datasetId) return [];
  try {
    const payload = await request(`/api/v1/datasets/${datasetId}/transactions?limit=${limit}`);
    return Array.isArray(payload?.items) ? payload.items : [];
  } catch {
    return [];
  }
}

export async function fetchDatasetAnalytics(datasetId, days = 30) {
  if (!datasetId) return null;
  try {
    return await request(`/api/v1/datasets/${datasetId}/analytics?days=${days}`);
  } catch {
    return null;
  }
}
