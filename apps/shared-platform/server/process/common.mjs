import { createHash, randomUUID } from 'node:crypto';

export const round = (n, d = 4) => {
  const p = 10 ** d;
  return Math.round((Number(n) + Number.EPSILON) * p) / p;
};

export const clamp = (value, low = 0, high = 1) => Math.min(Math.max(Number(value), low), high);

export const mean = (values) => values.length ? values.reduce((a, b) => a + Number(b), 0) / values.length : 0;

export function parseDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function daysBetween(a, b) {
  const da = parseDate(a), db = parseDate(b);
  if (!da || !db) return null;
  return (db.getTime() - da.getTime()) / 86_400_000;
}

export function riskRank(value) {
  return ({ LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 }[String(value || '').toUpperCase()] || 0);
}

export function highestRisk(values, fallback = 'LOW') {
  return [...values].sort((a, b) => riskRank(b) - riskRank(a))[0] || fallback;
}

export function percentile(values, q) {
  const xs = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!xs.length) return 0;
  if (xs.length === 1) return xs[0];
  const pos = (xs.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  return xs[base + 1] === undefined ? xs[base] : xs[base] + rest * (xs[base + 1] - xs[base]);
}

export function median(values) { return percentile(values, 0.5); }

export function robustStd(values) {
  const xs = values.map(Number).filter(Number.isFinite);
  if (xs.length < 2) return 0;
  const med = median(xs);
  const mad = median(xs.map((v) => Math.abs(v - med)));
  return 1.4826 * mad;
}

export function recencyWeight(ageDays, halfLifeDays = 90) {
  return 0.5 ** (Math.max(Number(ageDays) || 0, 0) / Math.max(halfLifeDays, 1));
}

export function weightedMean(pairs, fallback = 0) {
  const valid = pairs.map(([v, w]) => [Number(v), Math.max(Number(w), 0)]).filter(([v, w]) => Number.isFinite(v) && Number.isFinite(w));
  const total = valid.reduce((sum, [, w]) => sum + w, 0);
  return total ? valid.reduce((sum, [v, w]) => sum + v * w, 0) / total : fallback;
}

export function normalizedLowIsGood(value, minValue, maxValue) {
  if (maxValue <= minValue) return 1;
  return clamp(1 - (value - minValue) / (maxValue - minValue));
}

export function normalizedHighIsGood(value, minValue, maxValue) {
  if (maxValue <= minValue) return 1;
  return clamp((value - minValue) / (maxValue - minValue));
}

export function stableId(...parts) {
  const raw = parts.map((p) => String(p ?? '')).join('|');
  return createHash('sha1').update(raw).digest('hex').slice(0, 18);
}

export function makeResult({ capabilityId, domain, outputType, entityType, entityId, payload, confidence = 0, riskLevel = 'LOW', status = 'SUCCEEDED', inputRefs = [], model = 'integrated', message = null }) {
  return {
    capabilityId,
    domain,
    outputType,
    entityType,
    entityId: String(entityId),
    payload,
    confidence: clamp(confidence),
    riskLevel,
    status,
    inputRefs,
    model,
    message
  };
}

export function insufficient({ capabilityId, domain, outputType, entityType, entityId, reason, inputRefs = [] }) {
  return makeResult({
    capabilityId, domain, outputType, entityType, entityId,
    payload: { status: 'INSUFFICIENT_EVIDENCE', reason },
    confidence: 0,
    riskLevel: 'MEDIUM',
    status: 'SKIPPED',
    inputRefs,
    model: 'integrated'
  });
}

export function randomId(prefix) { return `${prefix}-${randomUUID()}`; }
