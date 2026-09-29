import { config } from './config.mjs';
import { getFirebaseServices } from './firebase.mjs';

export async function requireUser(req, res, next) {
  if (config.authMode === 'local') {
    if (process.env.NODE_ENV === 'production') {
      return res.status(500).json({ error: 'AUTH_MODE=local is disabled in production.' });
    }
    req.user = { uid: 'local-owner', email: 'local@development', role: 'owner' };
    return next();
  }

  const token = String(req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!token) return res.status(401).json({ error: 'Authentication required.' });

  const { auth, error } = getFirebaseServices();
  if (!auth) return res.status(503).json({ error: error?.message || 'Firebase authentication is unavailable.' });

  try {
    req.user = await auth.verifyIdToken(token);
    next();
  } catch {
    res.status(401).json({ error: 'Invalid or expired sign-in token.' });
  }
}

export async function requireBusinessAccess(req, res, next) {
  if (config.authMode === 'local') return next();

  const { db, error } = getFirebaseServices();
  if (!db) return res.status(503).json({ error: error?.message || 'Firestore is unavailable.' });

  const businessId = req.params.businessId || req.query.businessId;
  if (!businessId) return res.status(400).json({ error: 'businessId is required.' });

  const snap = await db.doc(`businesses/${businessId}/members/${req.user.uid}`).get();
  if (!snap.exists) return res.status(403).json({ error: 'You are not a member of this business.' });

  req.membership = snap.data();
  next();
}

export function requireDataEditor(req, res, next) {
  if (config.authMode === 'local') return next();
  const role = String(req.membership?.role || '').trim().toLowerCase();
  if (['owner', 'admin', 'editor', 'manager'].includes(role)) return next();
  return res.status(403).json({ error: 'Your workspace role does not allow business data changes.' });
}
