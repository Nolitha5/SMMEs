import fs from 'node:fs';
import { applicationDefault, cert, getApps, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { config, firebaseConfigurationState } from './config.mjs';

let state = { attempted: false, db: null, auth: null, error: null };

export function getFirebaseState() {
  return {
    ...firebaseConfigurationState(),
    connected: Boolean(state.db),
    error: state.error ? String(state.error.message || state.error) : null
  };
}

export function getFirebaseServices() {
  if (state.attempted) return state;
  state.attempted = true;

  const cfg = firebaseConfigurationState();
  if (!cfg.ready) {
    state.error = new Error(
      'Firebase Admin is not configured. Set FIREBASE_PROJECT_ID and either GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_SERVICE_ACCOUNT_JSON.'
    );
    return state;
  }

  try {
    let credential;
    if (config.firebaseServiceAccountJson) {
      credential = cert(JSON.parse(config.firebaseServiceAccountJson));
    } else if (config.credentialsPath && fs.existsSync(config.credentialsPath)) {
      credential = cert(JSON.parse(fs.readFileSync(config.credentialsPath, 'utf8')));
    } else {
      credential = applicationDefault();
    }

    const app = getApps()[0] || initializeApp({
      credential,
      projectId: config.firebaseProjectId
    });

    state.db = getFirestore(app);
    state.auth = getAuth(app);
  } catch (error) {
    state.error = error;
  }
  return state;
}
