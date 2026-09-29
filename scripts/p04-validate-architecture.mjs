import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const read = rel => JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
const fail = msg => { console.error(`P04 FAIL: ${msg}`); process.exit(1); };

const caps = read('architecture/capability-registry.v1.json');
if (caps.targetDomainCount !== 5) fail('expected 5 runtime domains');
if (caps.targetCapabilityCount !== 25 || caps.capabilities.length !== 25) fail('expected 25 capabilities');
const ids = caps.capabilities.map(x => x.capabilityId);
if (new Set(ids).size !== 25) fail('capability IDs must be unique');
const expected = [];
for (const p of ['D','I','P','R','C']) for (let n=1;n<=5;n++) expected.push(`${p}${n}`);
for (const id of expected) if (!ids.includes(id)) fail(`missing capability ${id}`);

const dep = read('architecture/dependency-map.v1.json');
for (const e of dep.edges) {
  if (!ids.includes(e.producer)) fail(`unknown producer ${e.producer}`);
  if (!ids.includes(e.consumer)) fail(`unknown consumer ${e.consumer}`);
}

const cols = read('architecture/collection-registry-target.v4.json').collections;
const names = new Set(cols.map(x=>x.collectionId));
for (const name of ['agentOutputs','agentState','agentRuns','agentEvents','agentRecommendations','approvalLog','outcomes','agentActions','auditLogs']) {
  if (!names.has(name)) fail(`missing collection ${name}`);
}

const aliases = read('architecture/compatibility-map.v1.json');
for (const [from,to] of Object.entries({system_events:'agentEvents',agent_outputs:'agentOutputs',agent_state:'agentState',agent_runs:'agentRuns',agent_recommendations:'agentRecommendations',approval_log:'approvalLog'})) {
  if (aliases.collectionAliases[from] !== to) fail(`missing alias ${from} -> ${to}`);
}

const eventSchema = read('contracts/agent-event.v1.schema.json');
const p = eventSchema.properties?.eventType?.pattern;
if (!p || !p.includes('\\.v')) fail('existing P03 event contract missing versioned event convention');
const events = read('architecture/event-registry.v1.json').events;
const rx = /^[a-z0-9-]+\.[a-z0-9-]+\.[a-z0-9-]+\.v[1-9][0-9]*$/;
for (const e of events) if (!rx.test(e.eventType)) fail(`event does not satisfy P03 pattern: ${e.eventType}`);

const d4 = read('contracts/demand-forecast.v1.schema.json');
for (const f of ['product_id','horizon_days','expected_qty','lower_bound','upper_bound','confidence','drivers','generated_at','source_version']) {
  if (!d4.required.includes(f)) fail(`D4 missing required field ${f}`);
}
const d4spec = read('architecture/d4-adapter-spec.v1.json');
if (d4spec.acceptedAliases.horizon !== 'horizon_days' || d4spec.acceptedAliases.source !== 'source_version') fail('D4 alias mapping incorrect');

const ip = read('architecture/inventory-procurement-adapter-spec.v1.json');
if (ip.I2.procurementView.projected_position !== 'inventory_position') fail('I2 projected_position mapping incorrect');
if (ip.I2.procurementView.recommended_qty !== 'suggested_reorder_qty') fail('I2 recommended_qty mapping incorrect');

const shared = read('contracts/shared-agent-output.v1.schema.json');
for (const f of ['businessId','capabilityId','sourceAgent','correlationId','idempotencyKey','stateId']) {
  if (!shared.required.includes(f)) fail(`SharedAgentOutput missing ${f}`);
}

console.log(`Capabilities: ${caps.capabilities.length}`);
console.log(`Dependency edges: ${dep.edges.length}`);
console.log(`Target/compat collections: ${cols.length}`);
console.log(`Versioned events: ${events.length}`);
console.log('Firebase v3 reconciliation: PASS');
console.log('Demand D4 boundary: PASS');
console.log('Inventory -> Procurement adapters: PASS');
console.log('P04_CANONICAL_ARCHITECTURE_OK');
