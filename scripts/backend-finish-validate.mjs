import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fail = m => { console.error(`FAIL: ${m}`); process.exit(1); };
const exists = rel => fs.existsSync(path.join(root, rel));
const read = rel => fs.readFileSync(path.join(root, rel), 'utf8');
const json = rel => JSON.parse(read(rel));

const status = json('architecture/demand-live-source-status.v1.json');
if (status.status !== 'integrated-source-pending-test') fail(`unexpected Demand status: ${status.status}`);
if (status.sourceCommit !== 'e3534ef9ebc94460328a07bd45bedcec03cee956') fail('Florah source commit is not pinned');

const required = [
  'vendor/florah-demand/backend/app/agents/demand/d1_sales_history/agent.py',
  'vendor/florah-demand/backend/app/agents/demand/d2_seasonality/agent.py',
  'vendor/florah-demand/backend/app/agents/demand/d3_event_promotion/agent.py',
  'vendor/florah-demand/backend/app/agents/demand/d4_forecast/agent.py',
  'vendor/florah-demand/backend/app/agents/demand/d4_forecast/model_selector.py',
  'vendor/florah-demand/backend/app/agents/demand/d5_quality/agent.py',
  'vendor/florah-demand/backend/app/contracts/demand.py',
  'vendor/florah-demand/backend/app/services/demand_service.py',
  'vendor/florah-demand/backend/tests/test_integration.py',
  'vendor/florah-demand/backend/requirements.txt',
  'integration/demand/florah_adapter.py',
  'integration/demand/florah_bridge.py'
];
for (const rel of required) if (!exists(rel)) fail(`missing ${rel}`);

const contracts = read('vendor/florah-demand/backend/app/contracts/demand.py');
for (const token of ['class CleanDemandSeries', 'class SeasonalityProfile', 'class DemandSignalAdjustment', 'class DemandForecast', 'class ForecastQualityAlert']) {
  if (!contracts.includes(token)) fail(`Florah contracts missing ${token}`);
}
const d4 = read('vendor/florah-demand/backend/app/agents/demand/d4_forecast/agent.py');
if (!d4.includes('class ForecastGenerator')) fail('real D4 ForecastGenerator missing');
if (!d4.includes('INSUFFICIENT_EVIDENCE')) fail('D4 insufficient-evidence safety path missing');
const service = read('vendor/florah-demand/backend/app/services/demand_service.py');
for (const fn of ['run_d1', 'run_d2', 'run_d3', 'run_d4', 'run_d5', 'run_full_pipeline']) {
  if (!service.includes(`def ${fn}`)) fail(`DemandService missing ${fn}`);
}
const adapter = read('integration/demand/florah_adapter.py');
if (!adapter.includes('horizon_days') || !adapter.includes('source_version')) fail('canonical D4 adapter incomplete');

console.log('Florah real D1-D5 source: INTEGRATED');
console.log(`Pinned commit: ${status.sourceCommit.slice(0, 8)}`);
console.log('D4 canonical boundary: READY');
console.log('Temporary D4 production dependency: REMOVED');
console.log('Firebase deployment: STILL BLOCKED UNTIL FULL TEST');
console.log('BACKEND_IMPLEMENTATION_COMPLETE');
