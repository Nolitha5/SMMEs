import type {
  BusinessDataRecord,
  DataSetDefinition,
  DataValidationResult,
  ProcessingReadiness,
  ProcessingResult,
  Workspace
} from '../types';
import { authMode, ensureClientAuth } from './firebase';

const API = import.meta.env.VITE_API_BASE_URL || '/api';
export const BUSINESS_ID = import.meta.env.VITE_BUSINESS_ID || 'dev-business';

async function headers() {
  const result: Record<string, string> = { 'Content-Type': 'application/json' };
  // Production defaults to Firebase auth in firebase.ts. Reuse that single
  // resolved mode here so the API can never silently fall back to local auth.
  if (authMode === 'firebase') {
    const user = (await ensureClientAuth())?.currentUser;
    if (!user) throw new Error('You are signed out.');
    result.Authorization = `Bearer ${await user.getIdToken()}`;
  }
  return result;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...(await headers()), ...(init?.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || `Request failed (${response.status})`) as Error & { details?: unknown };
    error.details = body.details;
    throw error;
  }
  return body as T;
}

export function loadWorkspace() {
  return request<Workspace>(`/businesses/${BUSINESS_ID}/workspace`);
}

export function decideRecommendation(
  recommendationId: string,
  payload: {
    decision: 'APPROVED' | 'MODIFIED' | 'REJECTED';
    reason?: string;
    modifiedAction?: Record<string, unknown>;
  }
) {
  return request(`/businesses/${BUSINESS_ID}/recommendations/${encodeURIComponent(recommendationId)}/decision`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function loadDataCatalog() {
  return request<{ datasets: DataSetDefinition[] }>(`/businesses/${BUSINESS_ID}/data`);
}

export function loadDataRecords(dataset: string, limit = 250) {
  return request<{ dataset: string; records: BusinessDataRecord[]; returned: number }>(
    `/businesses/${BUSINESS_ID}/data/${encodeURIComponent(dataset)}?limit=${limit}`
  );
}

export function validateDataImport(dataset: string, records: Array<Record<string, unknown>>) {
  return request<DataValidationResult>(`/businesses/${BUSINESS_ID}/data/${encodeURIComponent(dataset)}/validate`, {
    method: 'POST',
    body: JSON.stringify({ records })
  });
}

export function importData(dataset: string, records: Array<Record<string, unknown>>) {
  return request<{ ok: true; dataset: string; recordsWritten: number }>(
    `/businesses/${BUSINESS_ID}/data/${encodeURIComponent(dataset)}/import`,
    { method: 'POST', body: JSON.stringify({ records }) }
  );
}

export function addDataRecord(dataset: string, record: Record<string, unknown>) {
  return request<{ ok: true; id: string }>(`/businesses/${BUSINESS_ID}/data/${encodeURIComponent(dataset)}`, {
    method: 'POST',
    body: JSON.stringify({ record })
  });
}

export function updateDataRecord(dataset: string, recordId: string, record: Record<string, unknown>) {
  return request<{ ok: true; id: string }>(
    `/businesses/${BUSINESS_ID}/data/${encodeURIComponent(dataset)}/${encodeURIComponent(recordId)}`,
    { method: 'PUT', body: JSON.stringify({ record }) }
  );
}

export function loadProcessingReadiness() {
  return request<ProcessingReadiness>(`/businesses/${BUSINESS_ID}/process/readiness`);
}

export function processBusinessData() {
  return request<ProcessingResult>(`/businesses/${BUSINESS_ID}/process`, { method: 'POST', body: '{}' });
}
