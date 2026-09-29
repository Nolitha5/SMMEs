FIREBASE FOUNDATION P02 — SHARED REGISTRY

Purpose
-------
Creates the shared database registry for the 25-agent platform WITHOUT creating
fake customers, sales, stock, suppliers, or other operational records.

Adds:
- collectionRegistry (13 provisional shared collection contracts)
- agentRegistry/customer-engagement
- platformMeta/integration
- schemaVersion 2
- rules for registry access and append-only audit logs

Apply
-----
Copy/replace these files into the existing firebase-foundation-bootstrap folder:
- package.json
- firestore.rules
- scripts/p02-create-registry.mjs
- scripts/p02-verify-registry.mjs

Do NOT replace .env, service-account credentials, bootstrap-firestore.mjs, or .firebaserc.

Then run:
  npm run p02:registry
  npm run deploy:firestore
  npm run p02:verify

Expected final verification:
  P02 verification PASSED.
  Collection registry entries: 13
  Agent registry entries: 1
  Schema version: 2

The other 24 agents are intentionally NOT invented here. Their registry entries
and final ownership contracts will be added only after repository audit.
