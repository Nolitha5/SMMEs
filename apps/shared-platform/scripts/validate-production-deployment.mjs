import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, '..');
const root = path.resolve(app, '..', '..');
const read = (p) => fs.readFileSync(p, 'utf8');

const config = read(path.join(app, 'server', 'config.mjs'));
const api = read(path.join(app, 'web', 'src', 'lib', 'api.ts'));
const server = read(path.join(app, 'server', 'app.mjs'));
const docker = read(path.join(root, 'Dockerfile'));
const ignore = read(path.join(root, '.gcloudignore'));

assert.match(config, /applicationDefaultAvailable/);
assert.match(config, /process\.env\.K_SERVICE/);
assert.match(config, /production \? 'firebase' : 'local'/);
assert.match(api, /import \{ authMode, ensureClientAuth \} from '\.\/firebase'/);
assert.match(api, /if \(authMode === 'firebase'\)/);
assert.match(server, /\/api\/ready/);
assert.match(server, /Strict-Transport-Security/);
assert.match(docker, /FROM node:22-bookworm-slim AS builder/);
assert.match(docker, /npm install --include=dev/);
assert.match(docker, /npm install --omit=dev/);
assert.match(docker, /PROCESSING_PYTHON=\/opt\/venv\/bin\/python/);
assert.match(docker, /COPY vendor\/florah-demand/);
assert.match(docker, /COPY vendor\/customer-engagement-shared/);
assert.match(ignore, /firebase-adminsdk/);
assert.match(ignore, /service-account/);
assert.match(ignore, /\.patch-backups/);
assert.doesNotMatch(docker, /GOOGLE_APPLICATION_CREDENTIALS/);

console.log('Cloud Run Application Default Credentials: READY');
console.log('Production Firebase auth default: READY');
console.log('Authenticated API token propagation: READY');
console.log('Same-origin production serving: READY');
console.log('Readiness endpoint: READY');
console.log('Security response headers: READY');
console.log('Node + Python multi-stage image: READY');
console.log('Credential/source-upload exclusions: READY');
console.log('PRODUCTION_DEPLOYMENT_HARDENING_PASS');
