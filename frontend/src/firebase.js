let authInstance = null;

export async function getFirebaseAuth() {
  if (import.meta.env.VITE_AUTH_MODE !== 'firebase') return null;
  if (authInstance) return authInstance;
  const [{ initializeApp }, { getAuth }] = await Promise.all([
    import('firebase/app'),
    import('firebase/auth'),
  ]);
  const app = initializeApp({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  });
  authInstance = getAuth(app);
  return authInstance;
}
