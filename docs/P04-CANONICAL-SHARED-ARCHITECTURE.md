# P04 — Canonical Shared Architecture Lock

## Decision

The v3 Firebase foundation remains the migration base rather than being discarded. Procurement's richer exchange model is folded into it without creating two competing systems.

### Canonical exchange

- `agentOutputs`: immutable capability-output history.
- `agentState`: latest valid projection per capability/output/entity.
- `agentRuns`: execution trace.
- `agentEvents`: routing/trigger stream; this is the canonical equivalent of Procurement's `system_events`.
- `agentRecommendations`: human-review action proposals only.
- `approvalLog`: append-only human decisions.
- `outcomes`: observed results/evaluation feedback.

### Existing v3 collections retained with narrowed semantics

- `agentInsights`: compatibility/UI projection, not canonical analytical history.
- `agentActions`: execution/work command after approval or internal tasking, not the recommendation queue.
- `auditLogs`: security/operational audit only. Agent business history is reconstructed from outputs/runs/recommendations/events/outcomes.
- `syncQueue`: optional platform sync/retry metadata.

This lets Customer Engagement and the current Firebase foundation continue to work while Procurement's richer semantics are introduced through adapters.

## Identity model

There are five runtime domains and 25 narrow capabilities. A published output carries both:

- `sourceAgent`: runtime domain identity such as `customer-engagement`;
- `capabilityId`: D1-D5, I1-I5, P1-P5, R1-R5 or C1-C5.

This resolves the earlier ambiguity where Customer Engagement is one runtime agent containing C1-C5 while the project still describes 25 agents.

## Florah / Demand

D1/D2/D3/D5 are reserved but not invented. D4 is provisioned because Inventory, Pricing and Procurement already depend on it. Native field aliases are adapted at the boundary. Tomorrow, Florah's actual D4 replaces the fixture/provider without changing downstream contracts.

## Inventory / Procurement

Thobeka remains authoritative for I1-I5 calculations. Noosrat's Procurement view is satisfied through field adapters. No duplicate Inventory calculations are introduced.

## Pricing

Tiyani's current Flask/SQLite application contains useful scraping, price-history and deal-analysis implementation, but it is not yet the canonical P1-P5 shape. Priority 2 decomposes it behind P1-P5 adapters while shared production state moves to Firestore.

## Firebase safety

P04 deliberately has no deployment script. The current live schema v3 remains untouched until Priority 2 contract/integration tests pass.
