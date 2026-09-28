# Merge File Manifest — Procurement R1–R5

**Purpose.** This repository was built standalone. Several files under
`backend/app/contracts/`, `core/`, `data/`, `coordination/`, `governance/`,
`firebase/` and `.github/` are **shared platform code** in the Blueprint's
layout (p14). Merging them wholesale would overwrite another member's work.
This manifest states, per file, what may be merged as-is and what needs the
team lead to reconcile.

**Classification**

| Class | Meaning |
|---|---|
| **PROCUREMENT-OWNED** | Belongs to this domain. No other member should have a competing version |
| **SHARED-CONTRACT** | Cross-domain schema. One canonical version must win |
| **SHARED-INFRASTRUCTURE** | Platform plumbing every domain uses |
| **STANDALONE-DEMO-ONLY** | Exists so this repo runs alone; not part of the shared system |
| **DO-NOT-MERGE** | Local artefact |

**Action**

| Action | Meaning |
|---|---|
| **MERGE AS-IS** | Safe to take wholesale |
| **MERGE SELECTIVELY** | Take the Procurement portions only |
| **TEAM-LEAD RECONCILIATION REQUIRED** | Another member may have a competing version; compare before merging |
| **DO NOT MERGE** | Leave behind |

---

## 1. Procurement domain — safe to merge

| File | Class | Action | Note |
|---|---|---|---|
| `backend/app/agents/procurement/r1_supplier_comparator.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/agents/procurement/r2_supplier_reliability.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/agents/procurement/r3_lead_time_risk.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/agents/procurement/r4_purchase_order_recommender.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/agents/procurement/r5_delivery_invoice_reconciliation.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/agents/procurement/registry.py` | PROCUREMENT-OWNED | MERGE AS-IS | R1–R5 only |
| `backend/app/agents/procurement/__init__.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/app/services/analytics.py` | PROCUREMENT-OWNED | MERGE AS-IS | Percentiles/robust stats used only by R1–R3 |
| `backend/app/worker.py` | PROCUREMENT-OWNED | MERGE SELECTIVELY | Daily R2/R3 refresh; shared scheduler may want one worker entry point |
| `backend/tests/test_r1.py` … `test_r5.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `backend/tests/test_r1_malformed_records.py` | PROCUREMENT-OWNED | MERGE AS-IS | 19 tests |
| `backend/tests/test_workflow.py` | PROCUREMENT-OWNED | MERGE AS-IS | |
| `sample_data/suppliers.csv`, `supplier_quotes.csv`, `supplier_performance.csv`, `purchase_orders.csv`, `goods_receipts.csv`, `invoices.csv` | PROCUREMENT-OWNED | MERGE AS-IS | Procurement's slice of the shared seed |

## 2. Shared contracts — one canonical version must win

| File | Class | Action | Why |
|---|---|---|---|
| `backend/app/contracts/shared.py` | SHARED-CONTRACT | **TEAM-LEAD RECONCILIATION REQUIRED** | Defines `SharedAgentOutput`, `AgentRun`, `SystemEvent`, `Outcome`, collection constants and `state_id()`. **Every domain needs exactly one of these.** Procurement's version implements the Firebase p4 envelope verbatim and is a reasonable candidate for the canonical file, but it must be compared against any other member's version before either is taken |
| `backend/app/contracts/models.py` | SHARED-CONTRACT + PROCUREMENT-OWNED | **MERGE SELECTIVELY** | Mixed file. **Shared:** `AgentResult`, `AgentContext`, `AgentStatus`, `ApprovalDecision`, `ApprovalStatus`, `RiskLevel`, `ImportResult`. **Procurement-owned:** `Supplier`, `SupplierQuote`, `SupplierPerformance`, `SupplierRank`, `SupplierComparison`, `SupplierReliabilityScore`, `LeadTimeRisk`, `PurchaseRecommendation`, `PurchaseOrder`, `GoodsReceipt`, `SupplierInvoice`, `ProcurementException`. **Foreign contracts held as interfaces only** — `ReorderNeed`, `SafetyStockTarget`, `DemandForecast` (and `InventoryPosition` in `shared.py`): these are Inventory's and Demand's to own; take theirs, drop ours |
| `backend/app/contracts/__init__.py` | SHARED-CONTRACT | MERGE AS-IS | Empty |

## 3. Shared infrastructure — compare before merging

| File | Class | Action | Why |
|---|---|---|---|
| `backend/app/data/output_repository.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | The Firebase doc (p3) names a single *shared* `OutputRepository`. This implementation satisfies it — append-only outputs, latest state, batch write, ownership enforcement, `get_latest_output` — but all five domains must use **one** |
| `backend/app/data/repository.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Repository protocol + in-memory adapter, incl. `insert_if_absent` / `write_batch` that `OutputRepository` depends on |
| `backend/app/data/firestore_repository.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Firestore adapter; atomic `write_batch`, append-only `create()` |
| `backend/app/data/factory.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Backend selection |
| `backend/app/services/events.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | `system_events` publisher. Event **names** are cross-domain API — `purchase.recommendation.created`, `recommendation.approved`, `supplier.performance.updated`, `outcome.recorded` are Blueprint-specified and must not be renamed unilaterally |
| `backend/app/services/runs.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | `agent_runs` trace — Firebase p3 assigns this to the "shared runtime" |
| `backend/app/services/audit_history.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Composes the audit view from the six canonical collections. Domain-agnostic; useful to the whole team |
| `backend/app/services/data_quality.py` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | `validate_rows` / `screen_records` are generic; `PRIMARY_KEYS` lists Procurement collections and must be merged with other domains' entries |
| `backend/app/services/imports.py` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | Generic CSV import |
| `backend/app/services/storage.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Firebase Storage archive |
| `backend/app/coordination/coordinator.py` | SHARED-INFRASTRUCTURE + PROCUREMENT-OWNED | **MERGE SELECTIVELY** | `run_agent` / run-trace / publish wiring is the shared pattern; `recommend_purchase`, `reconcile`, `execute_purchase_recommendation`, `close_purchase_order`, `_raise_reconciliation_review` are Procurement workflows. In the shared build these become a Procurement coordinator sitting on a shared base |
| `backend/app/coordination/approval.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Firebase p3/p12: `approval_log` is written **only** by the shared approval service. One implementation for all domains |
| `backend/app/governance/policies.py` | SHARED-INFRASTRUCTURE + PROCUREMENT-OWNED | **MERGE SELECTIVELY** | `finalize_agent_result`, risk tiers and the evidence/action split are cross-domain governance. `second_review_required` and the PO-value threshold are Procurement policy |
| `backend/app/core/auth.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Firebase Auth + role check. One per system |
| `backend/app/core/config.py` | SHARED-INFRASTRUCTURE | **MERGE SELECTIVELY** | Shared: app/auth/repository/Firebase settings. Procurement-specific: `recommendation_ttl_hours`, `supplier_quote_ttl_days`, `max_po_value_without_second_review`, `allow_upstream_fixtures` |
| `backend/app/core/firebase_app.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Single firebase-admin initialization incl. the emulator credential path |
| `backend/app/api/routes.py` | SHARED-INFRASTRUCTURE + PROCUREMENT-OWNED | **MERGE SELECTIVELY** | **Shared:** `/health`, `/ready`, `/me`, `/agents/status`, `/agents/{id}/run`, `/recommendations*`, `/outputs/*`, `/runs/{id}`, `/audit`, `/events`, `/data/*`, `/imports/*`. **Procurement:** `/procurement/*`, `/suppliers/{id}/scorecard`, `/dashboard`. See §6 for the approve/modify/reject shape question |
| `backend/app/main.py` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | App factory, CORS, router mounting, startup bootstrap |
| `backend/app/agents/base.py` | SHARED-CONTRACT | **TEAM-LEAD RECONCILIATION REQUIRED** | `BaseAgent` protocol from Blueprint p18; all 25 agents inherit the same shape |

## 4. Firebase configuration — highest overwrite risk

| File | Class | Action | Why |
|---|---|---|---|
| `firebase/firestore.rules` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED — HIGHEST RISK** | **One rules file governs the whole database.** This version enumerates every collection with no catch-all, because a catch-all `allow write` silently defeats the `allow write: if false` on protected collections (Firestore ORs matching blocks). Merging another domain's rules by replacement would break Procurement's protections; merging ours by replacement would break theirs. **These must be combined by hand**, and the no-catch-all property preserved |
| `firebase/firestore.indexes.json` | SHARED-INFRASTRUCTURE | **MERGE SELECTIVELY** | Index arrays concatenate cleanly. Ours covers Firebase p12's required set for Procurement (`agent_state`, `agent_outputs`, `agent_recommendations`, `supplier_performance`, `system_events` ×2) plus `supplier_quotes` |
| `firebase/storage.rules` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Scopes `procurement-imports/{userId}`; other domains will add their own prefixes |
| `firebase.json` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Rules/index paths, hosting target and the emulator block (ports 9099/8080/9199) |
| `firebase/Dockerfile.emulators` | STANDALONE-DEMO-ONLY | MERGE SELECTIVELY | Exists because the Firestore emulator JVM will not start on this Windows host. Useful to any member on Windows; unnecessary on a Linux CI runner |

## 5. Platform, CI and frontend

| File | Class | Action | Why |
|---|---|---|---|
| `.github/workflows/ci.yml` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | One CI per repo. Ours: pytest → `npm ci` → Vitest → build → Docker build |
| `.github/workflows/deploy-staging.yml` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | `workflow_dispatch` only; never auto-fires |
| `docker-compose.yml` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Two services; the shared build will have more |
| `backend/Dockerfile` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | Generic FastAPI image |
| `frontend/Dockerfile`, `nginx.conf` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | Generic static build |
| `.dockerignore` | SHARED-INFRASTRUCTURE | MERGE AS-IS | Excludes `node_modules`/`.venv` from the build context — without it the in-container frontend build inherits host binaries |
| `.env.example` | SHARED-INFRASTRUCTURE | **MERGE SELECTIVELY** | Must gain the other domains' variables. **`ALLOW_UPSTREAM_FIXTURES=false` must be set for the shared system** |
| `.gitignore`, `Makefile` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | |
| `frontend/src/App.js` | STANDALONE-DEMO-ONLY + PROCUREMENT-OWNED | **MERGE SELECTIVELY** | Contains the shared app shell (nav, auth gate, dashboard) **and** Procurement's pages. In the shared UI, take the Procurement views (Suppliers, Recommendations, Purchase Orders, Audit) and drop our shell |
| `frontend/src/api.js`, `firebase.js`, `main.js`, `index.css`, `components/Badge.js`, `components/Login.js` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | Generic client, auth bootstrap and shell primitives; one canonical set |
| `frontend/package.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `index.html`, `vitest.setup.js` | SHARED-INFRASTRUCTURE | **TEAM-LEAD RECONCILIATION REQUIRED** | One frontend build per repo |
| `frontend/src/*.test.js`, `components/*.test.js` | PROCUREMENT-OWNED | MERGE SELECTIVELY | Keep the Procurement behaviour tests; the shell tests follow whichever shell wins |

## 6. Shared-architecture tests

| File | Class | Action | Why |
|---|---|---|---|
| `backend/tests/test_shared_architecture.py` | SHARED-INFRASTRUCTURE | **MERGE AS-IS (recommended)** | 60 tests pinning the envelope, append-only outputs, latest state, ownership, run trace, event names, idempotency, audit composition and the evidence/action split. **Valuable to every domain** — they are written against the shared contract, not against Procurement's algorithms |
| `backend/tests/test_firebase_emulator.py` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | Adapter/rules/auth/storage tests are shared; the Procurement e2e trace is ours |
| `backend/tests/test_governance_security.py` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | Auth and approval boundaries are shared; the R4 execution cases are ours |
| `backend/tests/test_contracts.py`, `test_services.py`, `conftest.py` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | |
| `backend/pytest.ini`, `requirements.txt` | SHARED-INFRASTRUCTURE | MERGE SELECTIVELY | **Note:** `pytest` was pinned down from 9.0.2 to 8.3.2 — the original pin was unresolvable |

## 7. Standalone-only — do not carry into the shared system unchanged

| File | Class | Action | Why |
|---|---|---|---|
| `sample_data/demand_forecasts.csv` | STANDALONE-DEMO-ONLY | **DO NOT MERGE** | **D4 is Demand's contract.** Exists only so Procurement runs alone |
| `sample_data/inventory_positions.csv` | STANDALONE-DEMO-ONLY | **DO NOT MERGE** | I1 is Inventory's |
| `sample_data/reorder_needs.csv` | STANDALONE-DEMO-ONLY | **DO NOT MERGE** | I2 is Inventory's |
| `sample_data/safety_stock_targets.csv` | STANDALONE-DEMO-ONLY | **DO NOT MERGE** | I3 is Inventory's |
| `sample_data/products.csv`, `inventory_snapshots.csv`, `inventory_movements.csv` | STANDALONE-DEMO-ONLY | **DO NOT MERGE** | Shared import/ingest layer owns these |
| `UPSTREAM_SEED` / `SHARED_CONTEXT_SEED` in `backend/app/data/bootstrap.py` | STANDALONE-DEMO-ONLY | **MERGE SELECTIVELY** | Gated by `ALLOW_UPSTREAM_FIXTURES`; keep the gate, keep the operational seed, drop the upstream seed |
| `UPSTREAM_IMPORTS` in `backend/app/api/routes.py` | STANDALONE-DEMO-ONLY | **MERGE SELECTIVELY** | Four import endpoints that publish D4/I1/I2/I3 on their owners' behalf. Already 403 in shared mode |
| `POST /demo/bootstrap` | STANDALONE-DEMO-ONLY | MERGE SELECTIVELY | Demo convenience |
| `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`, `__pycache__/`, `.pytest_cache/` | DO-NOT-MERGE | **DO NOT MERGE** | Build artefacts; already git-ignored |
| `PROJECT_MANIFEST.sha256` | DO-NOT-MERGE | **DO NOT MERGE** | Checksums of *this* repo's layout; meaningless after merge |
| `docs/source/*` | DO-NOT-MERGE | **DO NOT MERGE** | The team's own source documents; the shared repo has its own copy |

## 8. Documentation

| File | Class | Action |
|---|---|---|
| `docs/SHARED_FIREBASE_CONFORMANCE.md`, `REQUIREMENTS_TRACEABILITY_MATRIX.md`, this manifest | PROCUREMENT-OWNED | MERGE AS-IS — audit evidence for the team lead |
| `docs/INTEGRATION_CONTRACTS.md`, `TEAM_HANDOFF.md` | PROCUREMENT-OWNED | MERGE AS-IS |
| `README.md`, `docs/ARCHITECTURE.md`, `API.md`, `TESTING.md`, `PROJECT_DOCUMENTATION.md` | SHARED-INFRASTRUCTURE | **MERGE SELECTIVELY** — describe the whole app; take the Procurement sections |
| `docs/VALIDATION_REPORT.md`, `MERGE_READINESS_REPORT.md`, `STAGING_DEPLOYMENT.md` | PROCUREMENT-OWNED | MERGE AS-IS |

---

## 9. Merge-order recommendation

Following Blueprint p14 ("shared contracts are merged first"):

1. **Reconcile shared contracts** — `contracts/shared.py`, the shared half of
   `contracts/models.py`, `agents/base.py`. Agree one canonical set.
2. **Reconcile shared infrastructure** — `data/`, `coordination/approval.py`,
   `governance/policies.py`, `core/`, `services/{events,runs,audit_history}.py`.
3. **Combine `firestore.rules` by hand.** Highest risk. Preserve: no catch-all,
   protected collections backend-only, per-collection enumeration.
4. **Concatenate `firestore.indexes.json`.**
5. **Merge `agents/procurement/` as-is** — no conflicts expected.
6. **Take Procurement's frontend views**, discard our shell if another exists.
7. **Drop every STANDALONE-DEMO-ONLY fixture** and set
   `ALLOW_UPSTREAM_FIXTURES=false`.
8. **Run the shared-architecture suite** against the merged tree.

## 10. Limitation — no shared repository was available

The team's actual shared repository/branch is **not present in this workspace**,
and the workspace lock prevents looking for it. Therefore:

- **No Git merge, conflict test or integration build has been performed.**
- This manifest is a *static classification* based on reading this repository
  against the three source documents. It predicts where conflicts will arise;
  it does not prove they were resolved.
- Claims of "conflict-free merge" or "integration verified" would be unfounded
  and are **not** made.

What *is* established: this repository is **source-conformant**,
**database-ready** by the Firebase document's five-point definition (p13), and
**ready for team-lead merger review**. Actual Git compatibility requires the
target repository and branch.
