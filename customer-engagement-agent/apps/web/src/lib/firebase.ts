import { getApps, initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { initializeFirestore, persistentLocalCache, persistentMultipleTabManager, type Firestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

export const firebaseEnabled = import.meta.env.VITE_ENABLE_FIREBASE === 'true' && Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);
let firestore: Firestore | null = null;

export function getFirebaseServices() {
  if (!firebaseEnabled) return null;
  if (!firestore) {
    const app = getApps()[0] ?? initializeApp(firebaseConfig);
    firestore = initializeFirestore(app, { localCache: persistentLocalCache({ tabManager: persistentMultipleTabManager() }) });
  }
  const app = getApps()[0]!;
  return { db: firestore, auth: getAuth(app) };
}
