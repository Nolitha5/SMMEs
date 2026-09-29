import 'dotenv/config';
import { initializeApp, applicationDefault, getApps } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
if (!projectId) throw new Error('FIREBASE_PROJECT_ID is required in .env');
if (!getApps().length) initializeApp({ credential: applicationDefault(), projectId });
const db = getFirestore();

const [business, schema, integration] = await Promise.all([
  db.doc(`businesses/${businessId}`).get(),
  db.doc(`businesses/${businessId}/platformMeta/schema`).get(),
  db.doc(`businesses/${businessId}/platformMeta/integration`).get()
]);
if (!business.exists) throw new Error(`businesses/${businessId} does not exist`);
if (!schema.exists) throw new Error('platformMeta/schema does not exist');

const schemaData = schema.data();
if (Number(schemaData.schemaVersion) !== 3) {
  throw new Error(`Expected live schemaVersion 3 before finalization, found ${schemaData.schemaVersion}`);
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const demand = JSON.parse(fs.readFileSync(path.join(root,'architecture/demand-live-source-status.v1.json'),'utf8'));

console.log(`Project: ${projectId}`);
console.log(`Business: ${businessId}`);
console.log(`Live schema: ${schemaData.schemaVersion}`);
console.log(`Shared contract status: ${integration.exists ? integration.data().sharedContractStatus ?? 'unknown' : 'unknown'}`);
console.log('Firebase read-only connection: PASS');
console.log(`Florah Demand source: ${demand.status}`);
console.log(demand.deploymentAllowed === true
  ? 'Production deploy gate: OPEN'
  : 'Production deploy gate: CLOSED (live D1-D5 still pending)');
console.log('BACKEND_LIVE_PREFLIGHT_OK');
