import 'dotenv/config';
import { initializeApp, applicationDefault, getApps } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
if (!projectId) throw new Error('FIREBASE_PROJECT_ID is required in .env');

if (!getApps().length) {
  initializeApp({ credential: applicationDefault(), projectId });
}

const db = getFirestore();
const [businessSnap, schemaSnap, integrationSnap, collectionsSnap, agentsSnap] = await Promise.all([
  db.doc(`businesses/${businessId}`).get(),
  db.doc(`businesses/${businessId}/platformMeta/schema`).get(),
  db.doc(`businesses/${businessId}/platformMeta/integration`).get(),
  db.collection(`businesses/${businessId}/collectionRegistry`).get(),
  db.collection(`businesses/${businessId}/agentRegistry`).get()
]);

const requiredCollections = [
  'customers','products','inventory','transactions','orders','suppliers','feedback',
  'promotions','agentInsights','agentEvents','agentActions','syncQueue','auditLogs'
];
const presentCollections = new Set(collectionsSnap.docs.map(d => d.id));
const missing = requiredCollections.filter(id => !presentCollections.has(id));

if (!businessSnap.exists) throw new Error('Missing business document');
if (!schemaSnap.exists) throw new Error('Missing platformMeta/schema');
if (!integrationSnap.exists) throw new Error('Missing platformMeta/integration');
if (!agentsSnap.docs.some(d => d.id === 'customer-engagement')) throw new Error('Missing customer-engagement registry entry');
if (missing.length) throw new Error(`Missing collectionRegistry entries: ${missing.join(', ')}`);
if (schemaSnap.data().schemaVersion !== 2) throw new Error(`Expected schemaVersion 2, got ${schemaSnap.data().schemaVersion}`);

console.log('P02 verification PASSED.');
console.log(`Project: ${projectId}`);
console.log(`Business: ${businessId}`);
console.log(`Collection registry entries: ${collectionsSnap.size}`);
console.log(`Agent registry entries: ${agentsSnap.size}`);
console.log(`Schema version: ${schemaSnap.data().schemaVersion}`);
console.log(`Registered agent: customer-engagement`);
