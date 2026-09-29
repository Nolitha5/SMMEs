import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const demand = JSON.parse(fs.readFileSync(path.join(root,'architecture/demand-live-source-status.v1.json'),'utf8'));
if (demand.deploymentAllowed !== true || demand.status !== 'integrated-live-source-tested') {
  console.error('DEPLOY BLOCKED: real D1-D5 is integrated, but the full live-demand/system test has not passed yet.');
  process.exit(2);
}
for (const name of ['p07-validate-system-integration.mjs','backend-validate.mjs']) {
  const r = spawnSync(process.execPath,[path.join(root,'scripts',name)],{cwd:root,encoding:'utf8'});
  process.stdout.write(r.stdout||'');
  process.stderr.write(r.stderr||'');
  if (r.status !== 0) process.exit(r.status || 1);
}
console.log('BACKEND_DEPLOY_GATE_OPEN');
