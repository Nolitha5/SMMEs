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
const [businessSnap, schemaSnap, contractsMetaSnap, contractSnap, ownershipSnap, collectionsSnap] = await Promise.all([
  db.doc(`businesses/${businessId}`).get(),
  db.doc(`businesses/${businessId}/platformMeta/schema`).get(),
  db.doc(`businesses/${businessId}/platformMeta/contracts`).get(),
  db.collection(`businesses/${businessId}/contractRegistry`).get(),
  db.collection(`businesses/${businessId}/ownershipRegistry`).get(),
  db.collection(`businesses/${businessId}/collectionRegistry`).get()
]);

const requiredContracts = ['agent-event-v1','agent-insight-v1','agent-action-v1','audit-log-v1'];
const presentContracts = new Set(contractSnap.docs.map(d => d.id));
const missingContracts = requiredContracts.filter(id => !presentContracts.has(id));

const requiredOwnership = [
  'customers','products','inventory','transactions','orders','suppliers','feedback','promotions',
  'agentInsights','agentEvents','agentActions','syncQueue','auditLogs'
];
const presentOwnership = new Set(ownershipSnap.docs.map(d => d.id));
const missingOwnership = requiredOwnership.filter(id => !presentOwnership.has(id));

if (!businessSnap.exists) throw new Error('Missing business document');
if (!schemaSnap.exists) throw new Error('Missing platformMeta/schema');
if (!contractsMetaSnap.exists) throw new Error('Missing platformMeta/contracts');
if (missingContracts.length) throw new Error(`Missing contractRegistry entries: ${missingContracts.join(', ')}`);
if (missingOwnership.length) throw new Error(`Missing ownershipRegistry entries: ${missingOwnership.join(', ')}`);
if (schemaSnap.data().schemaVersion !== 3) throw new Error(`Expected schemaVersion 3, got ${schemaSnap.data().schemaVersion}`);
if (contractsMetaSnap.data().contractRegistryVersion !== 1) throw new Error('Expected contractRegistryVersion 1');

for (const contractId of requiredContracts) {
  const doc = contractSnap.docs.find(d => d.id === contractId);
  const data = doc.data();
  if (data.status !== 'active') throw new Error(`${contractId} is not active`);
  if (data.contractVersion !== 1) throw new Error(`${contractId} contractVersion is not 1`);
  if (!Array.isArray(data.requiredFields) || data.requiredFields.length < 8) {
    throw new Error(`${contractId} requiredFields is incomplete`);
  }
}

for (const collectionId of ['agentEvents','agentInsights','agentActions','auditLogs']) {
  const doc = collectionsSnap.docs.find(d => d.id === collectionId);
  if (!doc) throw new Error(`Missing collectionRegistry/${collectionId}`);
  if (!doc.data().contractId) throw new Error(`${collectionId} missing contractId`);
}

console.log('P03 verification PASSED.');
console.log(`Project: ${projectId}`);
console.log(`Business: ${businessId}`);
console.log(`Contract registry entries: ${contractSnap.size}`);
console.log(`Ownership registry entries: ${ownershipSnap.size}`);
console.log(`Schema version: ${schemaSnap.data().schemaVersion}`);
console.log(`Contract registry version: ${contractsMetaSnap.data().contractRegistryVersion}`);
console.log('Contracts: agent-event-v1, agent-insight-v1, agent-action-v1, audit-log-v1');
