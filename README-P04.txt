P04 — CANONICAL SHARED ARCHITECTURE LOCK

This build reconciles the deployed Firebase foundation v3 with the audited team branches.

IMPORTANT: P04 is local validation/design only. It does NOT deploy or modify Firestore.

Run:
  npm run p04:validate

Expected final line:
  P04_CANONICAL_ARCHITECTURE_OK

What is locked:
- 5 runtime domains / 25 agent capabilities
- canonical output/state/run/recommendation/approval/outcome contracts
- existing v3 agentEvents retained as routing event stream
- agentActions retained for execution work, not human recommendation queue
- auditLogs retained for security/operational audit
- Procurement snake_case paths mapped to Firebase camelCase targets
- Customer Engagement event/version compatibility mapped
- D4 provisional boundary locked without inventing Florah's algorithms
- Inventory -> Procurement field adapters specified
- Pricing P1-P5 identities reserved; Tiyani decomposition deferred to Priority 2

No Firebase credentials are included in this ZIP.
