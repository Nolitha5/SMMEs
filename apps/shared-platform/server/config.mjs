import 'dotenv/config';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, '..');
const production = process.env.NODE_ENV === 'production';

function env(name, fallback = '') {
  const value = process.env[name];
  return value == null || value === '' ? fallback : value;
}

export const config = Object.freeze({
  port: Number(env('PORT', production ? '8080' : '8790')),
  businessId: env('BUSINESS_ID', 'dev-business'),
  authMode: env('AUTH_MODE', production ? 'firebase' : 'local'),
  // In production the UI and API are served from the same Cloud Run origin,
  // therefore CORS is disabled unless WEB_ORIGIN is explicitly supplied.
  webOrigin: env('WEB_ORIGIN', production ? '' : 'http://localhost:5174'),
  firebaseProjectId: env('FIREBASE_PROJECT_ID', env('GOOGLE_CLOUD_PROJECT', '')),
  credentialsPath: env('GOOGLE_APPLICATION_CREDENTIALS', ''),
  firebaseServiceAccountJson: env('FIREBASE_SERVICE_ACCOUNT_JSON', ''),
  firebaseWebApiKey: env('FIREBASE_WEB_API_KEY', env('VITE_FIREBASE_API_KEY', '')),
  firebaseWebAuthDomain: env('FIREBASE_WEB_AUTH_DOMAIN', env('VITE_FIREBASE_AUTH_DOMAIN', '')),
  firebaseWebAppId: env('FIREBASE_WEB_APP_ID', env('VITE_FIREBASE_APP_ID', ''))
});

export function firebaseConfigurationState() {
  const explicit = config.credentialsPath;
  const credentialsPresent = explicit ? fs.existsSync(explicit) : false;
  const jsonConfigured = Boolean(config.firebaseServiceAccountJson);
  // Cloud Run provides Application Default Credentials through the service
  // identity. Do not require or ship a service-account JSON key in production.
  const applicationDefaultAvailable = Boolean(
    process.env.K_SERVICE || process.env.GOOGLE_CLOUD_PROJECT || process.env.GCLOUD_PROJECT
  );
  const credentialMode = jsonConfigured
    ? 'service-account-json'
    : credentialsPresent
      ? 'service-account-file'
      : applicationDefaultAvailable
        ? 'application-default'
        : 'unconfigured';

  return {
    projectId: config.firebaseProjectId || null,
    credentialsPathConfigured: Boolean(explicit),
    credentialsFilePresent: credentialsPresent,
    credentialsJsonConfigured: jsonConfigured,
    applicationDefaultAvailable,
    credentialMode,
    ready: Boolean(config.firebaseProjectId && (credentialsPresent || jsonConfigured || applicationDefaultAvailable))
  };
}
