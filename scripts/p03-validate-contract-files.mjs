import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const expected = {
  'contracts/agent-event.v1.schema.json': ['eventId','businessId','eventType','sourceAgent','payload','contractVersion','schemaVersion','correlationId','idempotencyKey','status','attemptCount','createdAt'],
  'contracts/agent-insight.v1.schema.json': ['insightId','businessId','insightType','sourceAgent','subjectType','subjectId','data','status','contractVersion','schemaVersion','createdAt','updatedAt'],
  'contracts/agent-action.v1.schema.json': ['actionId','businessId','actionType','sourceAgent','targetAgent','subjectType','subjectId','input','status','priority','contractVersion','schemaVersion','correlationId','idempotencyKey','createdAt','updatedAt'],
  'contracts/audit-log.v1.schema.json': ['logId','businessId','actorType','actorId','action','resourceType','resourceId','details','schemaVersion','correlationId','createdAt']
};

for (const [file, requiredFields] of Object.entries(expected)) {
  const parsed = JSON.parse(await readFile(resolve(file), 'utf8'));
  if (parsed.type !== 'object') throw new Error(`${file}: root type must be object`);
  if (!Array.isArray(parsed.required)) throw new Error(`${file}: required must be an array`);
  for (const field of requiredFields) {
    if (!parsed.required.includes(field)) throw new Error(`${file}: missing required field ${field}`);
    if (!parsed.properties?.[field]) throw new Error(`${file}: missing property definition for ${field}`);
  }
  if (parsed.additionalProperties !== false) throw new Error(`${file}: additionalProperties must be false`);
}

console.log('P03 local contract validation PASSED.');
console.log(`Validated schema files: ${Object.keys(expected).length}`);
