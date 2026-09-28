# Retail Procurement Agent — Agent 4 (R1–R5)

A complete, standalone implementation of **Agent 4: Procurement** for the supplied five-layer Agentic AI retail architecture. The project intentionally implements only Procurement and exposes stable contracts for the external Demand and Inventory teams.

## Scope

| Agent | Purpose | Primary output |
|---|---|---|
| R1 | Supplier Comparator | `SupplierComparison` |
| R2 | Supplier Reliability | `SupplierReliabilityScore` |
| R3 | Lead-Time Risk | `LeadTimeRisk` |
| R4 | Purchase Order Recommender | `PurchaseRecommendation` |
| R5 | Delivery & Invoice Reconciliation | `ProcurementException` / match result |

The implementation keeps the document's design principles: specialized agents, lightweight coordination, human approval for high-impact procurement actions, auditable decisions, deterministic/statistical methods before unnecessary LLM use, and safe failure when evidence is missing or stale.

## Five-layer mapping

1. **Governance:** approval states, risk tiers, audit events, fail-safe evidence checks, optional second review threshold.
2. **Information:** Firestore/in-memory repository adapters, CSV validation/import, supplier/quote/performance/PO/receipt/invoice data.
3. **Coordination:** `ProcurementCoordinator` routes R1→R2/R3→R4 and R5 workflows without embedding domain algorithms.
4. **Agent:** five independent R1–R5 Python components with typed outputs.
5. **Human Interface:** React + Vite + Tailwind procurement dashboard for supplier intelligence, recommendations, approvals, POs, reconciliation, imports and audit.

## External integration contracts

This repository **does not implement Demand or Inventory agents**. It accepts their published outputs:

- `I2 / ReorderNeed`
- `I3 / SafetyStockTarget`
- `D4 / DemandForecast`
- `I1 / InventoryPosition` (available; not required by current R4 logic)

R4 validates those contracts and refuses to issue a recommendation when required evidence is absent or stale.

## Shared Firestore architecture

Procurement persists exactly as one domain of the shared 25-agent system:

- every R1–R5 result is published through one `OutputRepository` into
  `agent_outputs` (append-only) and `agent_state` (latest projection) using the
  common `SharedAgentOutput` envelope;
- **R1–R3 are evidence contracts** — never review items, whatever their risk;
  elevated risk raises a `system_event`. **R4 is the Procurement action
  recommendation** and goes to `agent_recommendations`. **R5 is
  reconciliation/exception evidence**; only a resulting human action (a
  `ReconciliationReview` for a mismatch) becomes a recommendation;
- approvals go to `approval_log` via the approval service only; every
  invocation leaves an `agent_runs` trace; `system_events` carries routing
  triggers only; closed POs write `outcomes`;
- there is no audit collection — the Audit view is composed on read from the
  canonical collections;
- R4 reads D4/I2/I3 (and I1) from `agent_state` — never from Procurement-private
  collections — and cannot publish another domain's contract. The local
  D4/I1/I2/I3 fixtures and import endpoints are **DEV/TEST COMPATIBILITY ONLY**
  (`ALLOW_UPSTREAM_FIXTURES`, must be `false` in the shared system);
- Firestore rules make every exchange/governance collection backend-only.

See `docs/SHARED_FIREBASE_CONFORMANCE.md`.

## Quick start — backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

The in-memory development profile automatically loads `sample_data/`.

- API: `http://localhost:8000/api/v1`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

## Quick start — frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. Development defaults to demo authentication. Staging uses Firebase Authentication.

## Demonstration flow

1. Open **Recommendations** and run `SKU-100`.
2. R1 ranks active suppliers; R2/R3 evaluate every candidate; R4 produces a governed purchase recommendation.
3. Approve the R4 recommendation.
4. Execute it to create a purchase order.
5. Add/import goods receipt and invoice records.
6. Run R5 reconciliation from **Purchase Orders**.
7. Accept a clean or reviewed reconciliation and close the PO.
8. Closing the PO writes a new supplier-performance outcome so future R2/R3 scores use the actual result.

Seed data also contains:

- `PO-DEMO-001`: clean three-way match.
- `PO-DEMO-002`: under-delivery, price variance, defects and late delivery.

## Human-in-the-loop rule

R4 never creates a purchase order by itself. It generates `READY_FOR_REVIEW`; a manager must approve/modify it, then explicitly execute it. R5 mismatches also require review. Clean R5 matches may pass automatically because they are low-risk deterministic validation results, not commercial actions.

## Repository layout

```text
retail-procurement-agent/
├── backend/
│   ├── app/
│   │   ├── agents/procurement/     # R1–R5
│   │   ├── contracts/              # Shared + external contracts
│   │   ├── coordination/           # Routing, approvals, execution
│   │   ├── governance/             # Risk/approval/fail-safe policy
│   │   ├── data/                   # Memory + Firestore repositories
│   │   ├── services/               # Analytics, imports, quality, audit
│   │   └── api/                    # FastAPI routes
│   └── tests/
├── frontend/                       # React + Vite + Tailwind
├── firebase/                       # Auth-backed Firestore/Storage/Hosting rules
├── sample_data/                    # Deterministic staging/demo fixtures
├── docs/
├── .github/workflows/              # CI + staging deployment
└── docker-compose.yml
```

## Tests

Backend — 125 passed (68 Firebase emulator tests skip unless the emulators are running):

```bash
cd backend
pytest -q
```

Covers contracts, every procurement agent, stale/missing evidence, API behavior,
governance, approval/execution, R5 reconciliation, the full
recommendation→PO→receipt/invoice→reconciliation→close feedback loop, and the
authorization/governance boundaries (unauthenticated and unauthorized access,
execution blocked before approval, duplicate-execution safety, audit
completeness).

Frontend — 51 passed:

```bash
cd frontend
npm ci
npm run test -- --run
```

Covers the API client, supplier and scorecard rendering, R4 recommendation
rendering with confidence/risk/status, approval and rejection controls, the
gating of purchase-order creation, R5 match and mismatch results, and empty and
API-error states.

Firebase emulator integration — 68 passed (193 backend total with emulators
running). Exercises the real Firestore adapter, the real security rules, real
emulator-issued ID tokens under `AUTH_MODE=firebase`, Storage, and the full
shared-architecture end-to-end trace:

```bash
docker build -f firebase/Dockerfile.emulators -t procurement-emulators:local .
docker run -d --name procurement-emulators \
  -p 9099:9099 -p 8080:8080 -p 9199:9199 -p 4400:4400 \
  -v "$PWD/firebase.json:/project/firebase.json:ro" \
  -v "$PWD/firebase:/project/firebase:ro" \
  procurement-emulators:local
```

See `docs/TESTING.md` for the pytest invocation and `docs/VALIDATION_REPORT.md`
for the executed evidence, including the defects found while closing the Docker
and Firebase gaps and the items deliberately left unchanged.

## Staging target

- **Frontend:** Firebase Hosting
- **Authentication:** Firebase Authentication
- **Operational DB:** Cloud Firestore
- **Storage/rules:** Firebase Storage
- **Backend:** FastAPI on Google Cloud Run
- **Scheduled jobs:** Cloud Scheduler/Cloud Run trigger if required
- **CI/CD:** GitHub Actions

See `docs/STAGING_DEPLOYMENT.md` for exact configuration and acceptance checks.
