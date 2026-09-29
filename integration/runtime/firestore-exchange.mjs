import { Timestamp } from 'firebase-admin/firestore';
import {
  requiredString,
  canonicalStateId,
  normalizeSharedOutputCore,
  buildAgentStateCore,
  buildRecommendationCore
} from './exchange-core.mjs';

function toTimestamp(value, name) {
  if (value == null) return null;
  if (value instanceof Timestamp) return value;
  if (value instanceof Date) return Timestamp.fromDate(value);
  if (typeof value === 'string') {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) throw new Error(`${name} must be a valid date/time`);
    return Timestamp.fromDate(d);
  }
  if (typeof value?.toDate === 'function' && typeof value?.toMillis === 'function') return value;
  throw new Error(`${name} must be a Timestamp, Date or ISO string`);
}

export { canonicalStateId };

export function validateSharedAgentOutput(input) {
  const output = normalizeSharedOutputCore(input);
  output.generatedAt = toTimestamp(output.generatedAt, 'generatedAt');
  output.expiresAt = toTimestamp(output.expiresAt, 'expiresAt');
  return output;
}

export function buildAgentState(output) {
  const o = validateSharedAgentOutput(output);
  return buildAgentStateCore(o);
}

export function buildRecommendationFromOutput(output, action, status = 'READY_FOR_REVIEW') {
  const o = validateSharedAgentOutput(output);
  return buildRecommendationCore(o, action, status);
}

export async function publishAgentOutput(db, rawOutput, options = {}) {
  const output = validateSharedAgentOutput(rawOutput);
  const businessPath = `businesses/${output.businessId}`;
  const outputRef = db.doc(`${businessPath}/agentOutputs/${output.outputId}`);
  const stateRef = db.doc(`${businessPath}/agentState/${output.stateId}`);
  const recRef = options.recommendationAction
    ? db.doc(`${businessPath}/agentRecommendations/${output.outputId}`)
    : null;

  return db.runTransaction(async tx => {
    const existingOutput = await tx.get(outputRef);
    if (existingOutput.exists) {
      return { published: false, duplicate: true, outputId: output.outputId, stateId: output.stateId };
    }

    const stateSnap = await tx.get(stateRef);
    const recSnap = recRef ? await tx.get(recRef) : null;

    tx.create(outputRef, output);

    let stateUpdated = false;
    if (!stateSnap.exists) {
      tx.create(stateRef, buildAgentState(output));
      stateUpdated = true;
    } else {
      const current = stateSnap.data();
      const currentTime = current.generatedAt?.toMillis?.() ?? new Date(current.generatedAt).getTime();
      const nextTime = output.generatedAt.toMillis();
      if (!Number.isFinite(currentTime) || nextTime >= currentTime) {
        tx.set(stateRef, buildAgentState(output), { merge: false });
        stateUpdated = true;
      }
    }

    let recommendationCreated = false;
    if (recRef && recSnap && !recSnap.exists) {
      tx.create(recRef, buildRecommendationFromOutput(
        output,
        options.recommendationAction,
        options.recommendationStatus || 'READY_FOR_REVIEW'
      ));
      recommendationCreated = true;
    }

    return {
      published: true,
      duplicate: false,
      outputId: output.outputId,
      stateId: output.stateId,
      stateUpdated,
      recommendationCreated
    };
  });
}

export async function readLatestAgentState(db, businessId, capabilityId, outputType, entityId) {
  const stateId = `${capabilityId}:${outputType}:${entityId}`;
  const ref = db.doc(`businesses/${businessId}/agentState/${stateId}`);
  const snap = await ref.get();
  return snap.exists ? snap.data() : null;
}

export async function startAgentRun(db, run) {
  const now = toTimestamp(run.startedAt ?? new Date(), 'startedAt');
  const doc = {
    runId: requiredString(run.runId, 'runId'),
    businessId: requiredString(run.businessId, 'businessId'),
    capabilityId: requiredString(run.capabilityId, 'capabilityId'),
    sourceAgent: requiredString(run.sourceAgent, 'sourceAgent'),
    domain: requiredString(run.domain, 'domain'),
    entityType: requiredString(run.entityType, 'entityType'),
    entityId: requiredString(run.entityId, 'entityId'),
    startedAt: now,
    completedAt: null,
    status: 'RUNNING',
    durationMs: null,
    modelOrRuleVersion: requiredString(run.modelOrRuleVersion, 'modelOrRuleVersion'),
    inputRefs: Array.isArray(run.inputRefs) ? run.inputRefs : [],
    outputId: null,
    actorId: run.actorId || 'system',
    error: null,
    contractVersion: 1,
    schemaVersion: 4,
    correlationId: requiredString(run.correlationId, 'correlationId')
  };
  await db.doc(`businesses/${doc.businessId}/agentRuns/${doc.runId}`).create(doc);
  return doc;
}

export async function finishAgentRun(db, businessId, runId, patch) {
  const ref = db.doc(`businesses/${businessId}/agentRuns/${runId}`);
  const snap = await ref.get();
  if (!snap.exists) throw new Error(`agent run not found: ${runId}`);
  const current = snap.data();
  const completedAt = toTimestamp(patch.completedAt ?? new Date(), 'completedAt');
  const durationMs = Math.max(0, completedAt.toMillis() - current.startedAt.toMillis());
  const status = patch.status || 'SUCCEEDED';
  if (!['SUCCEEDED','FAILED'].includes(status)) throw new Error('finish status must be SUCCEEDED or FAILED');
  const update = {
    completedAt,
    durationMs,
    status,
    outputId: patch.outputId ?? current.outputId ?? null,
    error: patch.error ?? null
  };
  await ref.update(update);
  return { ...current, ...update };
}
