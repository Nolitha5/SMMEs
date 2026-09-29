import 'dotenv/config';
import { initializeApp, applicationDefault, getApps } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readJson = rel => JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
const confirm = String(process.env.CONFIRM_SCHEMA_V4 || '').toLowerCase() === 'true';
const demand = readJson('architecture/demand-live-source-status.v1.json');

if (!projectId) throw new Error('FIREBASE_PROJECT_ID is required in .env');
if (!confirm) throw new Error('Set CONFIRM_SCHEMA_V4=true only when intentionally finalizing the live backend.');
if (demand.deploymentAllowed !== true || demand.status !== 'integrated-live-source-tested') {
  throw new Error('Schema v4 registration is blocked until the tested real D1-D5 source gate is open.');
}
if (!getApps().length) initializeApp({ credential: applicationDefault(), projectId });
const db = getFirestore();
const schemaRef = db.doc(`businesses/${businessId}/platformMeta/schema`);
const schemaSnap = await schemaRef.get();
if (!schemaSnap.exists) throw new Error('platformMeta/schema does not exist.');
const current = Number(schemaSnap.data().schemaVersion);
if (current === 4) {
  console.log('Live schema is already v4; registration is idempotently complete.');
  console.log('BACKEND_SCHEMA_V4_REGISTERED');
  process.exit(0);
}
if (current !== 3) throw new Error(`Expected schema v3 before migration; found ${current}`);

const capsDoc = readJson('architecture/capability-registry.v1.json');
const target = readJson('architecture/collection-registry-target.v4.json');
const events = readJson('architecture/event-registry.v1.json');
const caps = capsDoc.capabilities || capsDoc.agents || [];
if (caps.length !== 25) throw new Error(`Capability registry must contain 25 entries; found ${caps.length}`);

const now = FieldValue.serverTimestamp();
let batch = db.batch();
let writes = 0;
const commitIfNeeded = async (force=false) => {
  if (writes >= 400 || (force && writes > 0)) {
    await batch.commit(); batch = db.batch(); writes = 0;
  }
};
const set = async (ref, data, opts={merge:true}) => {
  batch.set(ref, data, opts); writes += 1; await commitIfNeeded();
};

for (const c of target.collections) {
  await set(db.doc(`businesses/${businessId}/collectionRegistry/${c.collectionId}`), {
    businessId, collectionId:c.collectionId,
    pathTemplate:`businesses/{businessId}/${c.collectionId}/{documentId}`,
    purpose:c.purpose, authoritativeOwner:c.owner, status:c.status,
    businessScoped:true, schemaVersion:4, updatedAt:now
  });
  await set(db.doc(`businesses/${businessId}/ownershipRegistry/${c.collectionId}`), {
    businessId, collectionId:c.collectionId, ownershipStatus:c.status,
    authoritativeOwner:c.owner, crossAgentReadPolicy:'business-membership-required',
    crossAgentWritePolicy:c.owner.startsWith('platform.') ? 'platform-controlled' : 'authoritative-domain-only',
    schemaVersion:4, updatedAt:now
  });
}
for (const cap of caps) {
  const capabilityId = cap.capabilityId || cap.agent_id || cap.id;
  await set(db.doc(`businesses/${businessId}/capabilityRegistry/${capabilityId}`), {
    businessId, ...cap, capabilityId, schemaVersion:4, updatedAt:now, createdAt:now
  });
}
for (const [agentId, internalCapabilities] of [
  ['demand',['D1','D2','D3','D4','D5']],
  ['inventory',['I1','I2','I3','I4','I5']],
  ['pricing',['P1','P2','P3','P4','P5']],
  ['procurement',['R1','R2','R3','R4','R5']],
  ['customer-engagement',['C1','C2','C3','C4','C5']]
]) {
  await set(db.doc(`businesses/${businessId}/agentRegistry/${agentId}`), {
    businessId, agentId, kind:'top-level-agent', status:'integrated',
    databaseMode:'shared-firestore', interfaceMode:'shared-platform-shell',
    internalCapabilities, schemaVersion:4, updatedAt:now, createdAt:now
  });
}
for (const [contractId, collection, jsonSchemaPath] of [
  ['shared-agent-output-v1','agentOutputs','contracts/shared-agent-output.v1.schema.json'],
  ['agent-state-v1','agentState','contracts/agent-state.v1.schema.json'],
  ['agent-run-v1','agentRuns','contracts/agent-run.v1.schema.json'],
  ['agent-recommendation-v1','agentRecommendations','contracts/agent-recommendation.v1.schema.json'],
  ['approval-log-v1','approvalLog','contracts/approval-log.v1.schema.json'],
  ['outcome-v1','outcomes','contracts/outcome.v1.schema.json'],
  ['demand-forecast-v1','agentOutputs','contracts/demand-forecast.v1.schema.json'],
  ['competitor-price-signal-v1','agentOutputs','contracts/competitor-price-signal.v1.schema.json'],
  ['allowed-price-range-v1','agentOutputs','contracts/allowed-price-range.v1.schema.json'],
  ['elasticity-estimate-v1','agentOutputs','contracts/elasticity-estimate.v1.schema.json'],
  ['promo-price-candidate-v1','agentOutputs','contracts/promo-price-candidate.v1.schema.json'],
  ['price-recommendation-v1','agentRecommendations','contracts/price-recommendation.v1.schema.json']
]) {
  await set(db.doc(`businesses/${businessId}/contractRegistry/${contractId}`), {
    businessId, contractId, contractVersion:1, schemaVersion:4, status:'active',
    compatibility:'backward-compatible-within-major-version', collection, jsonSchemaPath,
    updatedAt:now, createdAt:now
  });
}
await set(db.doc(`businesses/${businessId}/platformMeta/contracts`), {
  businessId, contractRegistryVersion:2, schemaVersion:4,
  eventTypeConvention:'<domain>.<entity>.<verb>.v<major>',
  canonicalOutputLayer:['agentOutputs','agentState'],
  governanceLayer:['agentRecommendations','approvalLog','outcomes'],
  eventRegistryVersion:events.version, updatedAt:now
});
await set(db.doc(`businesses/${businessId}/platformMeta/integration`), {
  businessId, targetAgentCount:25, registeredCapabilityCount:25, topLevelAgentCount:5,
  sharedContractStatus:'active-v4', liveDemandIntegrated:true, schemaVersion:4, updatedAt:now
});
await set(schemaRef, {
  businessId, schemaVersion:4, registryVersion:2, contractRegistryVersion:2,
  architecture:'shared-firestore-event-driven', canonicalSchemaStatus:'active', updatedAt:now
});
await set(db.doc(`businesses/${businessId}`), { schemaVersion:4, updatedAt:now });
await commitIfNeeded(true);
console.log('Schema v4 registry finalization complete.');
console.log(`Capabilities registered: ${caps.length}`);
console.log(`Collections registered: ${target.collections.length}`);
console.log('No operational/sample data was created.');
console.log('BACKEND_SCHEMA_V4_REGISTERED');
