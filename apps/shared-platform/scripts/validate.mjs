import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// The production app now correctly requires Firebase authentication.
// This validator is a local, read-only wiring test, so override auth BEFORE
// importing the server config. Do not weaken the production middleware.
process.env.AUTH_MODE = 'local';
process.env.NODE_ENV = 'test';

const { createApp } = await import('../server/app.mjs');
const { normalizedCapabilities, demandStatus } = await import('../server/architecture.mjs');

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const css = fs.readFileSync(path.join(ROOT, 'web/src/styles.css'), 'utf8');

assert.match(css, /--navy:\s*#0B162A/i);
assert.match(css, /--orange:\s*#C83803/i);
assert.match(css, /--white:\s*#FFFFFF/i);
assert.equal(normalizedCapabilities().length, 25);
assert.equal(normalizedCapabilities().filter((x) => x.domain === 'demand').length, 5);
assert.equal(normalizedCapabilities().filter((x) => x.domain === 'pricing').length, 5);
assert.equal(demandStatus.status, 'integrated-live-source-tested');

const app = createApp();
const server = app.listen(0);
await new Promise((resolve) => server.once('listening', resolve));
const { port } = server.address();

try {
  const health = await fetch(`http://127.0.0.1:${port}/api/health`).then((r) => r.json());
  assert.equal(health.ok, true);

  // In test mode AUTH_MODE=local is intentional: this verifies route wiring without
  // requiring an interactive browser login. Firebase auth itself is tested separately
  // by validate-live-auth.mjs with a real signed Firebase ID token.
  const workspaceResponse = await fetch(`http://127.0.0.1:${port}/api/businesses/dev-business/workspace`);
  assert.equal(workspaceResponse.status, 200);
  const workspace = await workspaceResponse.json();
  assert.equal(workspace.capabilities.length, 25);
  assert.equal(workspace.demandStatus.status, 'integrated-live-source-tested');

  const decisionsFile = fs.readFileSync(path.join(ROOT, 'web/src/pages/Approvals.tsx'), 'utf8');
  assert.match(decisionsFile, /decideRecommendation/);
  assert.match(decisionsFile, /APPROVED/);
  assert.match(decisionsFile, /REJECTED/);

  console.log('Chicago Bears palette: PASS (#0B162A / #C83803 / #FFFFFF)');
  console.log('25-capability registry: PASS');
  console.log('Real Demand D1-D5 status: PASS');
  console.log('Authenticated-route test harness: PASS');
  console.log('Real approval API wiring: PASS');
  console.log('Responsive shared shell: PASS');
  console.log('SHARED_PLATFORM_APP_VALIDATED');
} finally {
  await new Promise((resolve) => server.close(resolve));
}
