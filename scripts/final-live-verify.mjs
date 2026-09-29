import 'dotenv/config';
import { applicationDefault, getApps, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
const projectId=process.env.FIREBASE_PROJECT_ID;
const businessId=process.env.BUSINESS_ID||'dev-business';
if(projectId!=='sme-agent-platform-dev') throw new Error(`Unexpected project ${projectId}`);
if(!getApps().length)initializeApp({credential:applicationDefault(),projectId});
const db=getFirestore();
const [schema,integration,caps,collections,agents,contracts]=await Promise.all([
  db.doc(`businesses/${businessId}/platformMeta/schema`).get(),
  db.doc(`businesses/${businessId}/platformMeta/integration`).get(),
  db.collection(`businesses/${businessId}/capabilityRegistry`).get(),
  db.collection(`businesses/${businessId}/collectionRegistry`).get(),
  db.collection(`businesses/${businessId}/agentRegistry`).get(),
  db.collection(`businesses/${businessId}/contractRegistry`).get()
]);
if(!schema.exists||Number(schema.data().schemaVersion)!==4)throw new Error('Live schema v4 verification failed');
if(!integration.exists||integration.data().sharedContractStatus!=='active-v4')throw new Error('Live integration metadata is not active-v4');
const capIds=new Set(caps.docs.map(d=>d.id));
for(const id of ['D1','D2','D3','D4','D5','I1','I2','I3','I4','I5','P1','P2','P3','P4','P5','R1','R2','R3','R4','R5','C1','C2','C3','C4','C5']){
  if(!capIds.has(id))throw new Error(`Missing live capability ${id}`);
}
if(caps.size!==25)throw new Error(`Expected 25 live capabilities, found ${caps.size}`);
if(collections.size<29)throw new Error(`Expected at least 29 collection registry docs, found ${collections.size}`);
for(const id of ['demand','inventory','pricing','procurement','customer-engagement']){
  if(!agents.docs.some(d=>d.id===id))throw new Error(`Missing top-level agent registry ${id}`);
}
if(contracts.size<12)throw new Error(`Expected at least 12 contract registry docs, found ${contracts.size}`);
console.log('Live schema v4: PASS');
console.log('25/25 capability registry: PASS');
console.log(`Collection registry: PASS (${collections.size})`);
console.log('Five top-level agents: PASS');
console.log(`Contract registry: PASS (${contracts.size})`);
console.log('Shared integration metadata active-v4: PASS');
console.log('No sample operational data required or created by this deployment.');
console.log('FINAL_FIREBASE_LIVE_VALIDATED');
