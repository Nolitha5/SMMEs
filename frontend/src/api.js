import { getFirebaseAuth } from './firebase.js';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function headers(extra = {}) {
  const out = { ...extra };
  if (import.meta.env.VITE_AUTH_MODE === 'firebase') {
    const auth = await getFirebaseAuth();
    if (auth?.currentUser) out.Authorization = `Bearer ${await auth.currentUser.getIdToken()}`;
  } else {
    out['X-Demo-User'] = 'manager@example.com';
  }
  return out;
}

export async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: await headers(options.headers || {}),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

export async function uploadCsv(collection, file) {
  const form = new FormData();
  form.append('file', file);
  return api(`/imports/${collection}`, { method: 'POST', body: form });
}
