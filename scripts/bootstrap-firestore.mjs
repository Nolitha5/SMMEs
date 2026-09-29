import 'dotenv/config';
import { initializeApp, applicationDefault } from 'firebase-admin/app';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';

const projectId = process.env.FIREBASE_PROJECT_ID;
const businessId = process.env.BUSINESS_ID || 'dev-business';
const businessName = process.env.BUSINESS_NAME || 'Development SME';
const ownerUid = (process.env.OWNER_UID || '').trim();
const seedSampleData = String(process.env.SEED_SAMPLE_DATA || 'false').toLowerCase() === 'true';

if (!projectId) {
  throw new Error('FIREBASE_PROJECT_ID is required in .env');
}

initializeApp({
  credential: applicationDefault(),
  projectId,
});

const db = getFirestore();
const businessRef = db.doc(`businesses/${businessId}`);

const baseDoc = {
  businessId,
  name: businessName,
  status: 'active',
  schemaVersion: 1,
  environment: 'development',
  updatedAt: FieldValue.serverTimestamp(),
};

await businessRef.set({
  ...baseDoc,
  createdAt: FieldValue.serverTimestamp(),
}, { merge: true });

await db.doc(`businesses/${businessId}/platformMeta/schema`).set({
  businessId,
  schemaVersion: 1,
  architecture: 'shared-firestore-event-driven',
  agentCountTarget: 25,
  createdBy: 'firebase-foundation-bootstrap',
  updatedAt: FieldValue.serverTimestamp(),
}, { merge: true });

if (ownerUid) {
  await db.doc(`businesses/${businessId}/members/${ownerUid}`).set({
    businessId,
    uid: ownerUid,
    role: 'owner',
    status: 'active',
    createdAt: FieldValue.serverTimestamp(),
    updatedAt: FieldValue.serverTimestamp(),
  }, { merge: true });
}

if (seedSampleData) {
  const batch = db.batch();
  const now = FieldValue.serverTimestamp();

  batch.set(db.doc(`businesses/${businessId}/customers/sample-customer`), {
    businessId,
    customerId: 'sample-customer',
    displayName: 'Sample Customer',
    marketingConsent: true,
    schemaVersion: 1,
    sourceAgent: 'bootstrap',
    createdAt: now,
    updatedAt: now,
  });

  batch.set(db.doc(`businesses/${businessId}/products/sample-product`), {
    businessId,
    productId: 'sample-product',
    name: 'Sample Product',
    active: true,
    schemaVersion: 1,
    sourceAgent: 'bootstrap',
    createdAt: now,
    updatedAt: now,
  });

  batch.set(db.doc(`businesses/${businessId}/inventory/sample-product`), {
    businessId,
    productId: 'sample-product',
    quantityOnHand: 10,
    schemaVersion: 1,
    sourceAgent: 'bootstrap',
    createdAt: now,
    updatedAt: now,
  });

  batch.set(db.doc(`businesses/${businessId}/transactions/sample-transaction`), {
    businessId,
    transactionId: 'sample-transaction',
    customerId: 'sample-customer',
    total: 25,
    currency: 'ZAR',
    schemaVersion: 1,
    sourceAgent: 'bootstrap',
    createdAt: now,
    updatedAt: now,
  });

  batch.set(db.doc(`businesses/${businessId}/feedback/sample-feedback`), {
    businessId,
    feedbackId: 'sample-feedback',
    customerId: 'sample-customer',
    text: 'Sample feedback for integration testing.',
    schemaVersion: 1,
    sourceAgent: 'bootstrap',
    createdAt: now,
    updatedAt: now,
  });

  await batch.commit();
}

console.log('Firebase foundation bootstrap complete.');
console.log(`Project: ${projectId}`);
console.log(`Business: businesses/${businessId}`);
console.log(`Owner membership created: ${ownerUid ? 'yes' : 'no (OWNER_UID empty)'}`);
console.log(`Sample data created: ${seedSampleData ? 'yes' : 'no'}`);
