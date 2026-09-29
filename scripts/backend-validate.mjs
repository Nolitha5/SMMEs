import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import {
  canonicalStateId,
  normalizeSharedOutputCore,
  buildAgentStateCore,
  buildRecommendationCore
} from '../integration/runtime/exchange-core.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readJson = rel => JSON.parse(fs.readFileSync(path.join(ROOT, rel), 'utf8'));
const fail = msg => { console.error(`FAIL: ${msg}`); process.exit(1); };

const p07 = spawnSync(process.execPath, [path.join(ROOT, 'scripts/p07-validate-system-integration.mjs')], {
  cwd: ROOT, encoding: 'utf8'
});
process.stdout.write(p07.stdout || '');
process.stderr.write(p07.stderr || '');
if (p07.status !== 0) fail('P07 regression gate failed');

const caps = readJson('architecture/capability-registry.v1.json');
const collections = readJson('architecture/collection-registry-target.v4.json');
const events = readJson('architecture/event-registry.v1.json');
const demand = readJson('architecture/demand-live-source-status.v1.json');
const rules = fs.readFileSync(path.join(ROOT, 'firestore.rules'), 'utf8');
const firestoreRuntime = fs.readFileSync(path.join(ROOT, 'integration/runtime/firestore-exchange.mjs'), 'utf8');
const indexes = readJson('firestore.indexes.json');

const capList = caps.capabilities || caps.agents || [];
if (capList.length !== 25) fail(`expected 25 capabilities, found ${capList.length}`);
if ((collections.collections || []).length < 29) fail('canonical collection registry is incomplete');
if ((events.events || []).length !== 14) fail('versioned event registry mismatch');

for (const required of ['agentOutputs','agentState','agentRuns','agentRecommendations','approvalLog','outcomes']) {
  if (!rules.includes(`match /${required}/`)) fail(`rules missing protected ${required} block`);
}
if (!rules.includes('allow write: if false;')) fail('protected server-authored writes are not blocked');
if ((indexes.indexes || []).length < 6) fail('expected canonical composite indexes');
for (const fn of ['publishAgentOutput','readLatestAgentState','startAgentRun','finishAgentRun']) {
  if (!firestoreRuntime.includes(`function ${fn}`)) fail(`Firestore runtime missing ${fn}`);
}

const sample = {
  outputId: 'D4-SKU-TEST-1',
  businessId: 'dev-business',
  capabilityId: 'D4',
  sourceAgent: 'demand',
  domain: 'demand',
  outputType: 'DemandForecast',
  entityType: 'product',
  entityId: 'SKU-TEST',
  payload: {
    product_id: 'SKU-TEST',
    horizon_days: 7,
    expected_qty: 100,
    lower_bound: 80,
    upper_bound: 120,
    confidence: 0.8,
    drivers: ['validation'],
    generated_at: '2026-09-29T00:00:00Z',
    source_version: 'provisional-validation'
  },
  inputRefs: ['fixture:validation'],
  confidence: 0.8,
  riskLevel: 'LOW',
  generatedAt: '2026-09-29T00:00:00Z',
  expiresAt: null,
  modelOrRuleVersion: 'validation-1',
  runId: 'run-validation',
  correlationId: 'corr-validation',
  idempotencyKey: 'idem-validation'
};
const normalized = normalizeSharedOutputCore(sample);
if (canonicalStateId(normalized) !== 'D4:DemandForecast:SKU-TEST') fail('canonical stateId mismatch');
const state = buildAgentStateCore(sample);
if (state.outputId !== sample.outputId || state.schemaVersion !== 4) fail('agentState projection mismatch');
const rec = buildRecommendationCore(
  { ...sample, capabilityId:'P5', sourceAgent:'pricing', domain:'pricing', outputType:'PriceRecommendation' },
  { productId:'SKU-TEST', proposedPrice:99.99 }
);
if (rec.status !== 'READY_FOR_REVIEW' || rec.schemaVersion !== 4) fail('recommendation projection mismatch');

console.log('Canonical Firestore runtime core: PASS');
console.log(`Composite indexes: ${indexes.indexes.length}`);
console.log('Server-authored exchange/governance rules: PASS');
console.log(`Florah Demand source: ${demand.status}`);
if (demand.deploymentAllowed !== true) {
  console.log('Production deploy gate: BLOCKED ONLY BY LIVE D1-D5 SOURCE');
}
console.log('BACKEND_COMPLETION_PREDEPLOY_READY');
