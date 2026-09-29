import 'dotenv/config';
import { applicationDefault, getApps, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
const expectedProject = 'sme-agent-platform-dev';
if (projectId !== expectedProject) throw new Error(`Refusing unexpected Firebase project: ${projectId || 'missing'}`);
const demand = JSON.parse(fs.readFileSync(path.join(root,'architecture/demand-live-source-status.v1.json'),'utf8'));
if (demand.status !== 'integrated-live-source-tested' || demand.deploymentAllowed !== true) {
  throw new Error('Real Demand test gate is not open.');
}
if (!getApps().length) initializeApp({credential:applicationDefault(),projectId});
const db=getFirestore();
const [business,schema,integration,members,caps]=await Promise.all([
  db.doc(`businesses/${businessId}`).get(),
  db.doc(`businesses/${businessId}/platformMeta/schema`).get(),
  db.doc(`businesses/${businessId}/platformMeta/integration`).get(),
  db.collection(`businesses/${businessId}/members`).limit(5).get(),
  db.collection(`businesses/${businessId}/capabilityRegistry`).limit(30).get()
]);
if(!business.exists) throw new Error(`businesses/${businessId} does not exist`);
if(!schema.exists) throw new Error('platformMeta/schema does not exist');
const version=Number(schema.data().schemaVersion);
if(![3,4].includes(version)) throw new Error(`Expected live schema v3 or v4, found ${version}`);
if(members.empty) throw new Error('No business membership exists; live workspace would be inaccessible.');
console.log(`Project: ${projectId}`);
console.log(`Business: ${businessId}`);
console.log(`Live schema before deploy: v${version}`);
console.log(`Existing capability registry docs: ${caps.size}`);
console.log(`Shared contract status: ${integration.exists ? integration.data().sharedContractStatus ?? 'unknown' : 'not-yet-v4'}`);
console.log('Business membership: PASS');
console.log('Credential + read-only Firestore connection: PASS');
console.log('Real Demand deployment gate: OPEN');
console.log('FINAL_FIREBASE_LIVE_PREFLIGHT_OK');
