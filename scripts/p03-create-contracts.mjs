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

const contracts = [
  {
    id: 'agent-event-v1',
    recordType: 'agentEvent',
    collection: 'agentEvents',
    purpose: 'Cross-agent domain event envelope',
    requiredFields: [
      'eventId','businessId','eventType','sourceAgent','payload','contractVersion',
      'schemaVersion','correlationId','idempotencyKey','status','attemptCount','createdAt'
    ],
    statusValues: ['pending','processing','processed','failed','dead-letter'],
    jsonSchemaPath: 'contracts/agent-event.v1.schema.json'
  },
  {
    id: 'agent-insight-v1',
    recordType: 'agentInsight',
    collection: 'agentInsights',
    purpose: 'Derived agent insight tied to a business entity',
    requiredFields: [
      'insightId','businessId','insightType','sourceAgent','subjectType','subjectId',
      'data','status','contractVersion','schemaVersion','createdAt','updatedAt'
    ],
    statusValues: ['active','superseded','expired','dismissed'],
    jsonSchemaPath: 'contracts/agent-insight.v1.schema.json'
  },
  {
    id: 'agent-action-v1',
    recordType: 'agentAction',
    collection: 'agentActions',
    purpose: 'Requested/recommended work handed between agents or the platform',
    requiredFields: [
      'actionId','businessId','actionType','sourceAgent','targetAgent','subjectType',
      'subjectId','input','status','priority','contractVersion','schemaVersion',
      'correlationId','idempotencyKey','createdAt','updatedAt'
    ],
    statusValues: ['proposed','approved','rejected','in-progress','completed','failed','cancelled'],
    jsonSchemaPath: 'contracts/agent-action.v1.schema.json'
  },
  {
    id: 'audit-log-v1',
    recordType: 'auditLog',
    collection: 'auditLogs',
    purpose: 'Append-only operational/security audit record',
    requiredFields: [
      'logId','businessId','actorType','actorId','action','resourceType','resourceId',
      'details','schemaVersion','correlationId','createdAt'
    ],
    statusValues: [],
    jsonSchemaPath: 'contracts/audit-log.v1.schema.json'
  }
];

const ownership = [
  ['customers', 'pending-repository-audit', null],
  ['products', 'pending-repository-audit', null],
  ['inventory', 'pending-repository-audit', null],
  ['transactions', 'pending-repository-audit', null],
  ['orders', 'pending-repository-audit', null],
  ['suppliers', 'pending-repository-audit', null],
  ['feedback', 'pending-repository-audit', null],
  ['promotions', 'pending-repository-audit', null],
  ['agentInsights', 'platform-shared-contract', 'platform'],
  ['agentEvents', 'platform-shared-contract', 'platform'],
  ['agentActions', 'platform-shared-contract', 'platform'],
  ['syncQueue', 'platform-shared', 'platform'],
  ['auditLogs', 'platform-core-append-only', 'platform']
];

const batch = db.batch();

for (const contract of contracts) {
  batch.set(db.doc(`businesses/${businessId}/contractRegistry/${contract.id}`), {
    businessId,
    contractId: contract.id,
    contractVersion: 1,
    schemaVersion: 1,
    status: 'active',
    compatibility: 'backward-compatible-within-major-version',
    ...contract,
    updatedAt: now,
    createdAt: now
  }, { merge: true });

  batch.set(db.doc(`businesses/${businessId}/collectionRegistry/${contract.collection}`), {
    contractId: contract.id,
    contractVersion: 1,
    ownershipStatus: contract.collection === 'auditLogs' ? 'platform-core-append-only' : 'platform-shared-contract',
    schemaVersion: 2,
    updatedAt: now
  }, { merge: true });
}

for (const [collectionId, ownershipStatus, authoritativeOwner] of ownership) {
  batch.set(db.doc(`businesses/${businessId}/ownershipRegistry/${collectionId}`), {
    businessId,
    collectionId,
    ownershipStatus,
    authoritativeOwner,
    crossAgentReadPolicy: 'business-membership-required',
    crossAgentWritePolicy: ownershipStatus === 'pending-repository-audit'
      ? 'provisional-until-repository-audit'
      : 'shared-contract-enforced',
    schemaVersion: 1,
    updatedAt: now,
    createdAt: now
  }, { merge: true });
}

batch.set(db.doc(`businesses/${businessId}/platformMeta/contracts`), {
  businessId,
  contractRegistryVersion: 1,
  envelopeStyle: 'cloudevents-inspired-firestore-native',
  eventTypeConvention: '<domain>.<entity>.<verb>.v<major>',
  agentIdConvention: 'kebab-case',
  idempotencyRequired: true,
  correlationIdRequired: true,
  causationIdSupported: true,
  auditLogsAppendOnly: true,
  eventDeliverySemantics: 'at-least-once-compatible-consumers-must-be-idempotent',
  finalAgentIdentityAttestation: 'pending-repository-audit-and-runtime-integration',
  updatedAt: now,
  createdAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}/platformMeta/schema`), {
  businessId,
  schemaVersion: 3,
  registryVersion: 1,
  contractRegistryVersion: 1,
  architecture: 'shared-firestore-event-driven',
  canonicalSchemaStatus: 'provisional-pending-repository-audit',
  updatedAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}/platformMeta/integration`), {
  contractRegistryVersion: 1,
  sharedContractStatus: 'active',
  repositoryAuditRequiredBeforeFinalOwnershipRules: true,
  updatedAt: now
}, { merge: true });

batch.set(db.doc(`businesses/${businessId}`), {
  schemaVersion: 3,
  updatedAt: now
}, { merge: true });

await batch.commit();

console.log('P03 shared agent contracts created successfully.');
console.log(`Project: ${projectId}`);
console.log(`Business: businesses/${businessId}`);
console.log(`Contract registry entries: ${contracts.length}`);
console.log(`Ownership registry entries: ${ownership.length}`);
console.log('Contract version: 1');
console.log('Schema version: 3');
console.log('No sample operational data was created.');
