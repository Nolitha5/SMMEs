import 'dotenv/config';
import assert from 'node:assert/strict';
import { getFirebaseServices } from '../server/firebase.mjs';
import { createApp } from '../server/app.mjs';

const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
const apiKey = process.env.VITE_FIREBASE_API_KEY;

assert.equal(projectId, 'sme-agent-platform-dev', 'Shared app is pointed at the wrong Firebase project.');
assert.ok(apiKey, 'VITE_FIREBASE_API_KEY is missing.');
assert.equal(process.env.AUTH_MODE, 'firebase', 'AUTH_MODE must be firebase for the live auth test.');

const { auth, db, error } = getFirebaseServices();
if (!auth || !db) throw new Error(error?.message || 'Firebase Admin connection is unavailable.');

// Resolve an existing business member that also exists in Firebase Authentication.
const membershipSnap = await db.collection(`businesses/${businessId}/members`).limit(25).get();
assert.ok(!membershipSnap.empty, `No members exist for ${businessId}.`);

const candidates = membershipSnap.docs
  .map((doc) => ({ uid: doc.id, ...(doc.data() || {}) }))
  .sort((a, b) => (a.role === 'owner' ? -1 : 0) - (b.role === 'owner' ? -1 : 0));

let verifiedMember = null;
for (const member of candidates) {
  try {
    const user = await auth.getUser(member.uid);
    verifiedMember = { member, user };
    break;
  } catch {
    // Try the next membership. This test never creates or modifies users.
  }
}
assert.ok(verifiedMember, 'No business membership maps to an existing Firebase Auth user.');

// Use the service-account signer to obtain a real Firebase ID token without knowing
// or changing the user's password. This is read-only with respect to Firestore/Auth data.
const customToken = await auth.createCustomToken(verifiedMember.user.uid);
const exchange = await fetch(
  `https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${encodeURIComponent(apiKey)}`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: customToken, returnSecureToken: true })
  }
);
const exchangeBody = await exchange.json().catch(() => ({}));
if (!exchange.ok) {
  throw new Error(`Firebase Web Auth token exchange failed (${exchange.status}): ${exchangeBody?.error?.message || 'unknown error'}`);
}
assert.ok(exchangeBody.idToken, 'Firebase Web Auth did not return an ID token.');

const app = createApp();
const server = app.listen(0);
await new Promise((resolve) => server.once('listening', resolve));
const { port } = server.address();

try {
  const response = await fetch(`http://127.0.0.1:${port}/api/businesses/${businessId}/workspace`, {
    headers: { Authorization: `Bearer ${exchangeBody.idToken}` }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(`Authenticated workspace request failed (${response.status}): ${body.error || 'unknown error'}`);
  }

  assert.equal(body.connected, true, 'Workspace API did not connect to live Firestore.');
  assert.equal(body.capabilities?.length, 25, 'Workspace API did not expose all 25 capabilities.');
  assert.equal(body.demandStatus?.status, 'integrated-live-source-tested', 'Demand still reports a stale source state.');

  console.log(`Firebase Auth user: PASS (${verifiedMember.user.uid})`);
  console.log(`Business membership: PASS (${businessId})`);
  console.log('Firebase ID-token verification: PASS');
  console.log('Authenticated live Firestore workspace: PASS');
  console.log('25/25 capabilities through live API: PASS');
  console.log('Demand live-source state through API: PASS');
  console.log('LIVE_WEB_AUTH_API_E2E_PASS');
} finally {
  await new Promise((resolve) => server.close(resolve));
}
