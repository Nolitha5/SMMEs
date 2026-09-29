import { initializeApp, getApps } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';

type ClientConfig = {
  authMode?: string;
  businessId?: string;
  firebase?: { apiKey?: string | null; authDomain?: string | null; projectId?: string | null; appId?: string | null } | null;
};

const staticConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || ''
};

export const authMode = import.meta.env.VITE_AUTH_MODE || (import.meta.env.PROD ? 'firebase' : 'local');
let resolvedConfig = { ...staticConfig };
let authInstance: Auth | null = null;
let resolvePromise: Promise<Auth | null> | null = null;

function complete(config: typeof resolvedConfig) {
  return Boolean(config.apiKey && config.authDomain && config.projectId && config.appId);
}

function initialise(config: typeof resolvedConfig) {
  if (!complete(config)) return null;
  const app = getApps()[0] || initializeApp(config);
  authInstance = getAuth(app);
  return authInstance;
}

export function firebaseClientConfigured() {
  return complete(resolvedConfig);
}

export function clientAuth() {
  if (authInstance) return authInstance;
  if (complete(resolvedConfig)) return initialise(resolvedConfig);
  return null;
}

export async function ensureClientAuth() {
  if (authMode !== 'firebase') return null;
  const existing = clientAuth();
  if (existing) return existing;
  if (!resolvePromise) {
    resolvePromise = (async () => {
      const response = await fetch('/api/client-config');
      if (!response.ok) return null;
      const body = await response.json() as ClientConfig;
      if (body.firebase) {
        resolvedConfig = {
          apiKey: body.firebase.apiKey || '',
          authDomain: body.firebase.authDomain || '',
          projectId: body.firebase.projectId || '',
          appId: body.firebase.appId || ''
        };
      }
      return initialise(resolvedConfig);
    })();
  }
  return resolvePromise;
}
