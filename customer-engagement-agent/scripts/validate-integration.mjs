import { readFile } from 'node:fs/promises';

const manifest = JSON.parse(await readFile(new URL('../agent.manifest.json', import.meta.url), 'utf8'));
const required = ['agentId', 'contractVersion', 'capabilities', 'reads', 'writes', 'publishesEvents'];
const missing = required.filter(key => !(key in manifest));
if (missing.length) throw new Error(`agent.manifest.json missing: ${missing.join(', ')}`);
if (manifest.agentId !== 'customer-engagement') throw new Error('Unexpected agentId.');
if (!Array.isArray(manifest.capabilities) || manifest.capabilities.length !== 5) throw new Error('Expected exactly five internal capabilities C1-C5.');
const ids = manifest.capabilities.map(item => item.id).join(',');
if (ids !== 'C1,C2,C3,C4,C5') throw new Error(`Capability order/IDs invalid: ${ids}`);
if (manifest.database !== 'shared-firebase-firestore') throw new Error('Manifest must target the shared Firebase database.');
if (manifest.finalInterface !== 'provided-by-shared-platform') throw new Error('Manifest must not claim its own final production UI.');
console.log(`INTEGRATION_OK ${manifest.agentId} contract=${manifest.contractVersion} capabilities=${ids}`);
