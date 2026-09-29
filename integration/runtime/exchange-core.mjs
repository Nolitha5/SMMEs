const RISKS = new Set(['LOW', 'MEDIUM', 'HIGH']);
const REVIEW_STATUSES = new Set([
  'DRAFT','READY_FOR_REVIEW','APPROVED','MODIFIED','REJECTED','EXECUTED','EXPIRED'
]);

export function requiredString(value, name) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${name} must be a non-empty string`);
  return value.trim();
}

export function canonicalStateId(output) {
  return `${output.capabilityId}:${output.outputType}:${output.entityId}`;
}

export function normalizeSharedOutputCore(input) {
  const output = structuredClone(input);
  requiredString(output.outputId, 'outputId');
  requiredString(output.businessId, 'businessId');
  if (!/^[DIPRC][1-5]$/.test(requiredString(output.capabilityId, 'capabilityId'))) {
    throw new Error('capabilityId must be D1-D5, I1-I5, P1-P5, R1-R5 or C1-C5');
  }
  requiredString(output.sourceAgent, 'sourceAgent');
  requiredString(output.domain, 'domain');
  requiredString(output.outputType, 'outputType');
  requiredString(output.entityType, 'entityType');
  requiredString(output.entityId, 'entityId');
  if (!output.payload || typeof output.payload !== 'object' || Array.isArray(output.payload)) {
    throw new Error('payload must be an object');
  }
  if (!Array.isArray(output.inputRefs)) throw new Error('inputRefs must be an array');
  if (typeof output.confidence !== 'number' || output.confidence < 0 || output.confidence > 1) {
    throw new Error('confidence must be between 0 and 1');
  }
  if (!RISKS.has(output.riskLevel)) throw new Error('riskLevel must be LOW, MEDIUM or HIGH');
  requiredString(output.modelOrRuleVersion, 'modelOrRuleVersion');
  requiredString(output.runId, 'runId');
  requiredString(output.correlationId, 'correlationId');
  requiredString(output.idempotencyKey, 'idempotencyKey');
  output.contractVersion = 1;
  output.schemaVersion = 4;
  output.stateId = canonicalStateId(output);
  return output;
}

export function buildAgentStateCore(output) {
  const o = normalizeSharedOutputCore(output);
  return {
    stateId: o.stateId,
    businessId: o.businessId,
    outputId: o.outputId,
    capabilityId: o.capabilityId,
    sourceAgent: o.sourceAgent,
    domain: o.domain,
    outputType: o.outputType,
    entityType: o.entityType,
    entityId: o.entityId,
    payload: o.payload,
    confidence: o.confidence,
    riskLevel: o.riskLevel,
    generatedAt: o.generatedAt,
    expiresAt: o.expiresAt ?? null,
    modelOrRuleVersion: o.modelOrRuleVersion,
    contractVersion: 1,
    schemaVersion: 4
  };
}

export function buildRecommendationCore(output, action, status = 'READY_FOR_REVIEW') {
  const o = normalizeSharedOutputCore(output);
  if (!REVIEW_STATUSES.has(status)) throw new Error(`invalid recommendation status: ${status}`);
  if (!action || typeof action !== 'object' || Array.isArray(action)) {
    throw new Error('action must be an object');
  }
  return {
    recommendationId: o.outputId,
    businessId: o.businessId,
    sourceOutputId: o.outputId,
    capabilityId: o.capabilityId,
    sourceAgent: o.sourceAgent,
    domain: o.domain,
    recommendationType: o.outputType,
    subjectType: o.entityType,
    subjectId: o.entityId,
    action,
    confidence: o.confidence,
    riskLevel: o.riskLevel,
    status,
    correlationId: o.correlationId,
    createdAt: o.generatedAt,
    updatedAt: o.generatedAt,
    expiresAt: o.expiresAt ?? null,
    contractVersion: 1,
    schemaVersion: 4
  };
}
