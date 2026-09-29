import { randomUUID } from 'node:crypto';
import { FieldValue, Timestamp } from 'firebase-admin/firestore';
import { getFirebaseServices } from './firebase.mjs';
import { getDataset, publicCatalog, validateRecords, normalizeRecord } from './data-registry.mjs';

function services() {
  const { db, error } = getFirebaseServices();
  if (!db) {
    const err = new Error(error?.message || 'Business data is unavailable because Firestore is not connected.');
    err.code = 'FIREBASE_UNAVAILABLE';
    throw err;
  }
  return db;
}

function clean(value) {
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value === 'object') {
    if (value instanceof Timestamp || typeof value.toDate === 'function') return value.toDate().toISOString();
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clean(item)]));
  }
  return value;
}

function collectionRef(businessId, datasetKey) {
  const dataset = getDataset(datasetKey);
  return services().collection(`businesses/${businessId}/${dataset.collection}`);
}

async function datasetCount(businessId, dataset) {
  try {
    const snapshot = await services().collection(`businesses/${businessId}/${dataset.collection}`).count().get();
    return Number(snapshot.data().count || 0);
  } catch {
    const snapshot = await services().collection(`businesses/${businessId}/${dataset.collection}`).limit(501).get();
    return snapshot.size;
  }
}

export async function loadDataCatalog(businessId) {
  const catalog = publicCatalog();
  const counts = await Promise.all(catalog.map((dataset) => datasetCount(businessId, dataset)));
  return catalog.map((dataset, index) => ({ ...dataset, count: counts[index] }));
}

export async function listDataRecords(businessId, datasetKey, limitCount = 250) {
  const dataset = getDataset(datasetKey);
  const limit = Math.min(Math.max(Number(limitCount) || 250, 1), 500);
  const snapshot = await collectionRef(businessId, datasetKey).limit(limit).get();
  const records = snapshot.docs.map((doc) => ({ id: doc.id, ...clean(doc.data()) }));
  records.sort((a, b) => String(b?._meta?.updatedAt || b?._meta?.createdAt || '').localeCompare(String(a?._meta?.updatedAt || a?._meta?.createdAt || '')));
  return { dataset: dataset.key, records, limit, returned: records.length };
}

async function checkReferences(businessId, datasetKey, normalized) {
  const dataset = getDataset(datasetKey);
  const refs = dataset.references || [];
  const errors = [];
  if (!refs.length || !normalized.length) return errors;
  const db = services();

  for (const ref of refs) {
    const ids = [...new Set(normalized.map((item) => item.record[ref.field]).filter(Boolean).map(String))];
    if (!ids.length) continue;
    const target = getDataset(ref.dataset);
    const found = new Set();
    for (let start = 0; start < ids.length; start += 250) {
      const slice = ids.slice(start, start + 250);
      const docRefs = slice.map((id) => db.doc(`businesses/${businessId}/${target.collection}/${id}`));
      const snaps = await db.getAll(...docRefs);
      snaps.forEach((snap) => { if (snap.exists) found.add(snap.id); });
    }
    for (const item of normalized) {
      const id = item.record[ref.field];
      if (!id || found.has(String(id))) continue;
      errors.push({ row: item.row, field: ref.field, message: `Unknown ${ref.label} ID: ${id}. Add the ${target.label.toLowerCase()} record first.` });
    }
  }
  return errors;
}

export async function validateBusinessData(businessId, datasetKey, records) {
  const result = validateRecords(datasetKey, records);
  if (!result.errors.length) result.errors.push(...await checkReferences(businessId, datasetKey, result.normalized));
  return {
    valid: result.errors.length === 0,
    rowCount: records.length,
    validCount: result.normalized.length,
    errors: result.errors.slice(0, 200),
    warnings: result.warnings.slice(0, 200),
    preview: result.normalized.slice(0, 10).map(({ id, record }) => ({ id, ...record }))
  };
}


async function markDataChanged(businessId) {
  await services().doc(`businesses/${businessId}`).set({
    analysisStatus: 'NEEDS_PROCESSING',
    dataUpdatedAt: FieldValue.serverTimestamp()
  }, { merge: true });
}

async function audit(businessId, actor, eventType, payload) {
  const db = services();
  const id = randomUUID();
  await db.doc(`businesses/${businessId}/auditLogs/${id}`).set({
    auditId: id,
    eventType,
    actorId: actor,
    payload,
    createdAt: FieldValue.serverTimestamp()
  });
}

export async function importBusinessData({ businessId, datasetKey, records, actor }) {
  const validation = validateRecords(datasetKey, records);
  if (!validation.errors.length) validation.errors.push(...await checkReferences(businessId, datasetKey, validation.normalized));
  if (validation.errors.length) {
    const error = new Error('Import contains invalid records. Fix the listed rows before importing.');
    error.code = 'VALIDATION_FAILED';
    error.details = validation.errors.slice(0, 200);
    throw error;
  }

  const db = services();
  const dataset = getDataset(datasetKey);
  let written = 0;
  for (let start = 0; start < validation.normalized.length; start += 400) {
    const batch = db.batch();
    for (const item of validation.normalized.slice(start, start + 400)) {
      const ref = db.doc(`businesses/${businessId}/${dataset.collection}/${item.id}`);
      batch.set(ref, {
        ...item.record,
        _meta: {
          source: 'csv import',
          updatedAt: new Date().toISOString(),
          updatedBy: actor,
          lastImportAt: new Date().toISOString()
        }
      }, { merge: true });
      written += 1;
    }
    await batch.commit();
  }

  await markDataChanged(businessId);
  await audit(businessId, actor, 'BUSINESS_DATA_IMPORTED', { dataset: dataset.key, recordsWritten: written });
  return { ok: true, dataset: dataset.key, recordsWritten: written, warnings: validation.warnings.slice(0, 200), analysisStatus: 'NEEDS_PROCESSING' };
}

export async function saveBusinessDataRecord({ businessId, datasetKey, input, actor, existingId = null }) {
  const result = normalizeRecord(datasetKey, input, 1);
  if (result.errors.length) {
    const error = new Error('Record validation failed.');
    error.code = 'VALIDATION_FAILED';
    error.details = result.errors;
    throw error;
  }
  const referenceErrors = await checkReferences(businessId, datasetKey, [{ ...result, row: 1 }]);
  if (referenceErrors.length) {
    const error = new Error('Record validation failed.');
    error.code = 'VALIDATION_FAILED';
    error.details = referenceErrors;
    throw error;
  }
  if (existingId && existingId !== result.id) {
    const error = new Error('Record identity fields cannot be changed. Create a new record instead.');
    error.code = 'IDENTITY_CHANGE';
    throw error;
  }

  const db = services();
  const dataset = getDataset(datasetKey);
  const ref = db.doc(`businesses/${businessId}/${dataset.collection}/${result.id}`);
  const before = await ref.get();
  const now = new Date().toISOString();
  const previousMeta = before.exists ? clean(before.data()?._meta || {}) : {};
  await ref.set({
    ...result.record,
    _meta: {
      ...previousMeta,
      source: before.exists ? previousMeta.source || 'manual' : 'manual',
      createdAt: previousMeta.createdAt || now,
      createdBy: previousMeta.createdBy || actor,
      updatedAt: now,
      updatedBy: actor
    }
  }, { merge: false });

  await markDataChanged(businessId);
  await audit(businessId, actor, before.exists ? 'BUSINESS_DATA_UPDATED' : 'BUSINESS_DATA_ADDED', { dataset: dataset.key, recordId: result.id });
  return { ok: true, id: result.id, record: { id: result.id, ...result.record }, warnings: result.warnings, analysisStatus: 'NEEDS_PROCESSING' };
}
