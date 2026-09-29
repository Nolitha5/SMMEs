import 'dotenv/config';
import { initializeApp, applicationDefault, getApps } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';

const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';

if (!projectId) throw new Error('FIREBASE_PROJECT_ID is required in .env');

if (!getApps().length) {
  initializeApp({ credential: applicationDefault(), projectId });
}

const db = getFirestore();
const now = FieldValue.serverTimestamp();

const collections = [
  ['customers', 'Shared customer profiles and consent/preferences'],
  ['products', 'Shared product/catalog records'],
  ['inventory', 'Current stock state and availability'],
  ['transactions', 'Sales/transaction records'],
  ['orders', 'Order lifecycle records'],
  ['suppliers', 'Supplier master data'],
  ['feedback', 'Customer feedback and complaints'],
  ['promotions', 'Promotion/campaign definitions and status'],
  ['agentInsights', 'Derived insights produced by agents'],
  ['agentEvents', 'Cross-agent domain events'],
  ['agentActions', 'Recommended/requested agent actions'],
  ['syncQueue', 'Cloud-visible sync/retry metadata where required'],
  ['auditLogs', 'Append-only security/operational audit events']
];

const batch = db.batch();

for (const [collectionId, purpose] of collections) {
  batch.set(db.doc(`businesses/${businessId}/collectionRegistry/${collectionId}`), {
    businessId,
    collectionId,
    pathTemplate: `businesses/{businessId}/${collectionId}/{documentId}`,
    purpose,
    businessScoped: true,
    status: 'provisional',
    ownershipStatus: collectionId.startsWith('agent') || collectionId === 'auditLogs' || collectionId === 'syncQueue'
      ? 'platform-shared'
      : 'pending-repository-audit',
    schemaVersion: 1,
    updatedAt: now,
    createdAt: now
  }, { merge: true });
}

batch.set(db.doc(`businesses/${businessId}/agentRegistry/customer-engagement`), {
  businessId,
  agentId: 'customer-engagement',
  name: 'Customer Engagement Agent',
  status: 'integration-ready',
  kind: 'top-level-agent',
  interfaceMode: 'shared-platform-shell',
  databaseMode: 'shared-firestore',
  internalCapabilities: [
    { id: 'C1', name: 'Customer Segmentation' },
    { id: 'C2', name: 'Retention Risk' },
    { id: 'C3', name: 'Promotion Recommender' },
    { id: 'C4', name: 'Next Best Action' },
    { id: 'C5', name: 'Feedback & Sentiment' }
  ],
  readsDeclared: ['customers', 'transactions', 'products', 'inventory', 'feedback'],
  writesDeclared: ['agentInsights', 'agentEvents', 'agentActions'],
  integrationContractVersion: 1,
  schemaVersion: 1,
  updatedAt: now,
  createdAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}/platformMeta/integration`), {
  businessId,
  targetAgentCount: 25,
  registeredAgentCount: 1,
  databaseMode: 'shared-firestore',
  interfaceMode: 'shared-platform-shell',
  eventMode: 'firestore-event-driven',
  registryVersion: 1,
  repositoryAuditRequiredBeforeFinalSchema: true,
  updatedAt: now,
  createdAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}/platformMeta/schema`), {
  businessId,
  schemaVersion: 2,
  registryVersion: 1,
  architecture: 'shared-firestore-event-driven',
  agentCountTarget: 25,
  canonicalSchemaStatus: 'provisional-pending-repository-audit',
  updatedAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}`), {
  schemaVersion: 2,
  updatedAt: now
}, { merge: true });

await batch.commit();

console.log('P02 registry created successfully.');
console.log(`Project: ${projectId}`);
console.log(`Business: businesses/${businessId}`);
console.log(`Collection registry entries: ${collections.length}`);
console.log('Agent registry entries: 1 (customer-engagement)');
console.log('Schema version: 2');
console.log('No sample operational data was created.');
