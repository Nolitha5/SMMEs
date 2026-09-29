# 25-Agent Backend Completion Workspace

This is the cumulative backend workspace. It already includes the validated
P04-P07 architecture and integration gates and adds the production Firestore
runtime, schema-v4 security rules, indexes, registry migration and deployment
guard.

## Current state

The available backend is pre-deployment ready. Production deployment remains
intentionally blocked until Florah's real D1-D5 implementation replaces the
provisional Demand boundary.

This is one backend priority, not a new series of micro-priorities.

## What is already complete

- 25-capability registry and 41 dependency edges
- canonical shared exchange/governance contracts
- Inventory -> Procurement adapters and core chain
- actual Customer Engagement C1-C5 runtime integration
- Pricing P1-P5 decomposition, guardrails and approval flow
- cross-domain governance/system integration gate
- canonical Firestore runtime (`agentOutputs`, `agentState`, `agentRuns`,
  `agentRecommendations`, `approvalLog`, `outcomes`)
- schema-v4 Firestore rules and indexes
- read-only live Firebase preflight
- idempotent schema-v4 registry finalization script
- hard production deployment gate while live Demand is absent

## Commands

`npm run backend:validate`
Runs every local regression/integration gate and validates the production
Firestore runtime/rules/indexes. It does not contact Firebase and does not write
anything.

`npm run backend:preflight-live`
Connects to the configured Firebase project read-only and verifies the existing
live schema-v3 foundation. It performs no writes.

`npm run backend:deploy-gate`
Must remain blocked until Florah D1-D5 is integrated.

`npm run backend:register-v4`
Writes schema-v4 registry metadata only. It is additionally protected by
`CONFIRM_SCHEMA_V4=true` and the live-Demand gate.

Do not run `deploy:firestore` or `backend:register-v4` until the live Demand
integration patch has opened the gate.
