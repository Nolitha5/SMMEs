# Procurement Team Handoff

This repository owns **only Agent 4 / Procurement**.

## What the Procurement developer owns

- R1 Supplier Comparator
- R2 Supplier Reliability
- R3 Lead-Time Risk
- R4 Purchase Order Recommender
- R5 Delivery & Invoice Reconciliation
- Procurement API, dashboard, approvals, audit, tests and staging configuration

## What Procurement does not own

- Demand implementation (D1–D5)
- Inventory implementation (I1–I5)
- Pricing implementation (P1–P5)
- Customer Engagement implementation (C1–C5)

## Required upstream contracts

Other developers only need to publish valid records for:

- `ReorderNeed` (I2)
- `SafetyStockTarget` (I3)
- `DemandForecast` (D4)

See `INTEGRATION_CONTRACTS.md` for exact fields.

## Outputs for other domains / shared platform

Procurement publishes:

- `SupplierComparison` (R1)
- `SupplierReliabilityScore` (R2)
- `LeadTimeRisk` (R3)
- `PurchaseRecommendation` (R4)
- `ProcurementException` plus actual close/performance facts (R5)

Approved R4 results create purchase orders only after explicit manager execution. R5 close writes supplier-performance facts that can be shared with Inventory exception handling if the full system is integrated later.

## Integration rule

Do not import another team's agent classes. Integrate through the Pydantic contract schemas / persisted contract records / API boundaries only. Contract changes should be coordinated and CI-tested before merge.

## Shared Firestore handoff matrix

**R1–R3 = evidence contracts. R4 = the Procurement action recommendation.
R5 = reconciliation/exception evidence; only a resulting human action becomes a
recommendation.**

**R1** — READ `suppliers`, `supplier_quotes`. PUBLISH `SupplierComparison`. WRITE `agent_outputs`, `agent_state`.

**R2** — READ `supplier_performance`, `goods_receipts`, R5 delivery facts. PUBLISH `SupplierReliabilityScore`. WRITE `agent_outputs`, `agent_state`.

**R3** — READ `supplier_performance`, current delay facts, R5 delivery facts, R2 `SupplierReliabilityScore`. PUBLISH `LeadTimeRisk`. WRITE `agent_outputs`, `agent_state`, `system_events` when an operational signal is warranted (`procurement.evidence.risk_elevated`).

**R4** — READ `suppliers`, `supplier_quotes`, D4 `DemandForecast`, I1 `InventoryPosition`, I2 `ReorderNeed`, I3 `SafetyStockTarget`, R1 `SupplierComparison`, R2 `SupplierReliabilityScore`, R3 `LeadTimeRisk`. PUBLISH `PurchaseRecommendation`. WRITE `agent_outputs`, `agent_state`, `agent_recommendations`, `system_events`.

**R5** — READ `purchase_orders`, `goods_receipts`, `invoices`, approved R4 `PurchaseRecommendation`. PUBLISH `ProcurementException`, delivery/reconciliation facts. WRITE `agent_outputs`, `agent_state`, `supplier_performance`, `outcomes`, `system_events`. **ONLY creates an `agent_recommendation` if R5 produces a separate explicit human action requiring approval** — the `ReconciliationReview` for a mismatch. A clean match raises none.

R1–R3 never create approval records. `system_events` holds triggers only; the
audit trail is composed on read from the canonical collections.

**D4/I1/I2/I3 local fixture and import publishing is standalone test support
only** (`ALLOW_UPSTREAM_FIXTURES`, default true for development, must be false
in the shared system). Procurement is never their producer.

Full semantics, ownership rules, indexes, rules and integration steps:
`SHARED_FIREBASE_CONFORMANCE.md`.

## Exact integration instructions

1. Set `AUTH_MODE=firebase`, `REPOSITORY_BACKEND=firestore`,
   `FIREBASE_PROJECT_ID`, credentials, **and `ALLOW_UPSTREAM_FIXTURES=false`**
   before the process starts.
2. Deploy `firebase/firestore.rules` and `firebase/firestore.indexes.json`.
   Ensure no other domain ships a catch-all `allow write` — it would defeat the
   backend-only protection on the shared collections.
3. Demand publishes `agent_state/D4:DemandForecast:{product_id}`; Inventory
   publishes `I1:InventoryPosition:…`, `I2:ReorderNeed:…`,
   `I3:SafetyStockTarget:…` — all in the `SharedAgentOutput` envelope.
4. Consume Procurement outputs from `agent_state` by `state_id` or subscribe to
   `system_events` by `event_type`.
5. Approvals via `POST /recommendations/{id}/decision`; execution via
   `POST /recommendations/{id}/execute`. Never write `approval_log` directly.
6. Mint `role` custom claims (`owner_manager` / `admin` / `procurement_manager`).

## Validation state at handoff

Executed and passing locally:

- Backend suite — 193 passed with emulators (125 core + 68 Firebase integration); 125 passed / 68 skipped without
- **Shared Firebase architecture — CONFORMANT, DATABASE-READY.** One `OutputRepository`, append-only `agent_outputs`, latest `agent_state`, `agent_recommendations`, `approval_log`, `agent_runs`, `system_events`, `outcomes`; ownership enforced in code; backend-only Firestore rules; full input-to-output trace reconstructed from Firestore in the emulator
- Frontend suite — 51 passed, 0 failed, 0 skipped
- Vite production build — success
- Live browser regression — dashboard → supplier intelligence → R4 → approval → PO creation → R5 clean → R5 mismatch → audit
- Authorization and governance boundary tests — 21 passed (demo auth) plus 4 more under real Firebase tokens
- **Docker — PASSED, execution validated.** Both images build; Compose stack runs; containerized procurement smoke workflow passed including the approval gate and idempotency
- **Firebase — PASSED, local emulator validated.** Real Firestore adapter, real security rules, real emulator-issued ID tokens under `AUTH_MODE=firebase`, and Storage
- **R1 malformed-record handling — FOUND → FIXED → REGRESSION VERIFIED.** Schema-less supplier and quote documents no longer fail the comparison with HTTP 500; they are screened out against the contract models and reported with a per-record reason. 19 focused tests, 2 emulator-backed tests, mutation-checked, and verified live against Firestore

No known functional defect remains open.

## Running the emulator suite

```bash
docker build -f firebase/Dockerfile.emulators -t procurement-emulators:local .
docker run -d --name procurement-emulators \
  -p 9099:9099 -p 8080:8080 -p 9199:9199 -p 4400:4400 \
  -v "$PWD/firebase.json:/project/firebase.json:ro" \
  -v "$PWD/firebase:/project/firebase:ro" \
  procurement-emulators:local
```

Emulators run in a container because the Firestore emulator JVM cannot start on
the Windows validation host (`sun.nio.ch.UnixDomainSockets` / "Unable to
establish loopback connection"). On a Linux CI runner it can run natively. See
`TESTING.md` for the pytest invocation.

## Open items for the integration environment

| Item | Why it is open | Risk if skipped |
|---|---|---|
| Cloud-side Firebase configuration | Emulators prove the rules language and token handling, not a real project's rules deployment, IAM, quotas or custom-claim provisioning | **Medium** — staging must confirm claims are actually minted with `role` |
| Version control | Repository has no `.git` | **Medium** — must be initialized before merge |
| Emulator suite in CI | The image and tests exist; no CI job wires them up yet | **Low** — the suite runs on demand today |
| `npm audit` moderate advisories | Only fix is a breaking major upgrade | **Low** — needs a team-lead decision |

### Note on the demo authentication profile

`AUTH_MODE=demo` grants the `owner_manager` role to every caller with no
credential, and accepts the caller-supplied `X-Demo-User` header as identity. It
exists for local development only and must never be enabled in any shared or
internet-reachable environment. Staging and production must set
`AUTH_MODE=firebase`.

This is now proven rather than asserted: against the Auth emulator with
`AUTH_MODE=firebase`, the backend rejects missing, malformed and non-bearer
credentials, ignores `X-Demo-User` entirely, and propagates the `role` custom
claim from a genuine ID token.
