# Validation Report

Date: 2026-09-09
Scope: Agent 4 — Procurement R1–R5

Every line below records an **executed** result. Where something was found by
reading rather than running, it says so explicitly and is not counted as passing.

Docker and Firebase, carried as NOT TESTED in the previous revision, are now
execution-validated — see the Docker and Firebase sections below.

## Source-code validation

- Python application and tests compiled with `python -m compileall`.
- JSON configuration files parsed successfully.
- GitHub Actions YAML files parsed successfully.

## Automated backend tests

Command:

```bash
cd backend
pytest -q
```

Result without emulators (the default developer run):

```text
125 passed, 0 failed, 68 skipped in 2.35s
```

Result with the Firebase emulator suite running:

```text
193 passed, 0 failed, 0 skipped in 82.66s
```

Breakdown:

| Area | Tests |
|---|---|
| R1–R5 agents | 12 |
| Contracts (I2/I3/D4 + internal) | 4 |
| API | 3 |
| Services (imports, daily worker) | 2 |
| Workflow (end-to-end, idempotency) | 2 |
| Authorization & governance boundaries | 21 |
| R1 malformed-record handling | 19 |
| Shared Firebase architecture | 55 |
| **Core subtotal** | **118** |
| Firebase emulator integration | 68 |
| **Total with emulators** | **186** |

The 68 emulator tests skip automatically unless `FIRESTORE_EMULATOR_HOST` and
`FIREBASE_AUTH_EMULATOR_HOST` are set, so the default run stays fast and needs no
Docker.

## Shared-architecture alignment against the specification — CORRECTED, VERIFIED

Direct review against `25_Agent_Firebase_Database_Architecture.pdf` found four
semantic differences in the first conformance pass. All four are corrected;
every claim below was executed.

| # | Correction | Executed evidence |
|---|---|---|
| 1 | **R1–R3 never write `agent_recommendations`.** Routing is by `output_type` only; `finalize_agent_result` forces `requires_approval=False` on evidence. MEDIUM/HIGH raises `procurement.evidence.risk_elevated` | 9 parametrized in-memory cases (R1/R2/R3 × LOW/MEDIUM/HIGH) — no recommendation, present in outputs+state; R4 consumes normally; Firestore e2e asserts no R1–R3 approval records; Docker smoke: `agent_recommendations` agents = `R4` only |
| 2 | **R5 evidence/action split.** Clean MATCH → no recommendation, closes directly. MISMATCH → exception event + separate `ReconciliationReview` action (`source_output_id` → R5 output); closure 409 until approved | In-memory: clean/mismatch/blocked-until-approved/reuse-per-output; Firestore: `test_shared_r5_mismatch_raises_review_action_in_firestore`; 2 new Vitest cases prove the UI approves the review, not the evidence, and closes a clean match with no approval call; live UI: mismatch → Accept → PO-DEMO-002 CLOSED |
| 3 | **`system_events` is not the audit log.** Bookkeeping events (`data.*`, `demo.*`, `job.*`) removed. Audit history composed on read from `agent_runs`, `agent_outputs`, `agent_recommendations`, `approval_log`, `system_events`, `outcomes` | `test_system_events_carry_no_bookkeeping_records`; `test_audit_history_reconstructs_full_lifecycle_without_audit_collection` asserts no `audit_events` collection and all six sources; Firestore e2e steps 29–30; live Audit UI shows `recommendation.raised` / `recommendation.approved` / `outcome.recorded` interleaved with triggers |
| 4 | **Upstream fixtures are DEV/TEST only.** `ALLOW_UPSTREAM_FIXTURES` gates bootstrap seeding, the import endpoints (403) and `seed_upstream_contract()` (raises) | Three gate tests, one per path |

Collection names: `goods_receipts` and `invoices` only; `supplier_invoices` and
`audit_events` exist nowhere. No dual writes.

## Shared Firebase architecture — CONFORMANT, EXECUTION VALIDATED

Full specification and mapping: `SHARED_FIREBASE_CONFORMANCE.md`.

| Requirement | Evidence |
|---|---|
| Canonical collections | `supplier_invoices` → `invoices`; `audit_events` → `system_events`; `agent_status` removed (derived from `agent_runs`); I2/I3/D4 read from `agent_state`, not private collections |
| One `SharedAgentOutput` envelope | All 15 required fields; `AgentResult` extended, not replaced — 63 pre-existing tests still green |
| One `OutputRepository` | All five agents publish through `publish()`; `_store_result` removed from the coordinator |
| `agent_outputs` append-only | `insert_if_absent` (Firestore `create()`); republish with different content leaves history untouched |
| `agent_state` latest-only | Deterministic `state_id`; older-by-`generated_at` retry cannot regress state |
| Atomic writes | `write_batch` — Firestore batch commit; in-memory under one lock |
| `agent_recommendations` | R4/R5 always; R1–R3 only when governance flags them; carries `source_output_id`, `domain`, `schema_version` |
| `approval_log` | Sole writer `ApprovalService`; status + journal in one batch; `schema_version` |
| `agent_runs` | Every invocation: RUNNING → SUCCEEDED/FAILED, duration, versions, `input_refs`, `output_id`, bounded error |
| `system_events` | 9 event types, deterministic ids where a natural key exists |
| `outcomes` | Written at close, references `performance_id`, no duplication |
| Ownership | `OwnershipViolation` on foreign domain/agent/output_type; fixtures via separate `seed_upstream_contract` |
| Rules | No catch-all; 7 protected collections backend-only; shared context read-only; default-deny — 24 emulator rules tests |
| Indexes | 7 composite indexes, each backing a real query |
| Timestamps | All persisted timestamps generated server-side in the backend (UTC); no client timestamp is authoritative for agent or governance records |
| Freshness | 72-hour R4 policy unchanged; `expires_at` enforced by the repository |
| Traceability | R4 `input_refs` carry exact D4/I2/I3 and R1/R2/R3 output ids; trace reconstructed from Firestore alone |
| Idempotency | 8 retry scenarios — output, event, approval, execution, close, reconcile |
| Phase 25 e2e on Firestore | 27-step trace passed in `test_shared_architecture_end_to_end_trace` |
| Docker on shared architecture | Smoke read I2 from `agent_state`, R4 carried upstream `input_refs`, `agent_runs` + `system_events` present |
| Live browser on Firestore | Dashboard → supplier intelligence → R4 → approval → PO → R5 MATCH → R5 MISMATCH → audit; exchange records verified directly in the emulator |

### Fixture-freshness issue found and fixed

Sample upstream fixtures carried a fixed `generated_at` of 2026-09-08. Six days
later they exceeded the 72-hour window, so the R4 happy-path test would have
failed today regardless of this work. Demo fixtures are synthetic, so bootstrap
now stamps them "published now"; CSV imports through the API keep the file's
own `generated_at` so freshness enforcement sees genuine provenance.

### Firestore rules trap avoided

Firestore ORs every matching rule block. The previous `match /{document=**}`
catch-all with `allow write: if procurementRole()` would have silently overridden
`allow write: if false` on the protected collections. The rules now enumerate
every collection explicitly and rely on default-deny; the emulator test
`test_rules_unlisted_collection_is_denied_by_default` guards against the
catch-all being reintroduced.

The suite covers all R1–R5 agents, contracts, fail-safe behavior, API endpoints,
approval/execution, idempotency, three-way reconciliation, import evidence
checksums, daily supplier score refresh, the full procurement feedback loop, and
the authorization/governance boundaries described below.

## Authorization and governance boundary tests

`backend/tests/test_governance_security.py` — 21 tests, all passing:

- Firebase auth mode rejects a missing `Authorization` header (401).
- Firebase auth mode rejects a non-bearer `Authorization` header (401).
- Firebase auth mode ignores `X-Demo-User` spoofing — a caller cannot downgrade
  to demo auth (401).
- Invalid-token handling maps to 401 (firebase-admin verification stubbed).
- Demo mode's authentication bypass is asserted explicitly as intended
  development-only behavior.
- `require_manager` admits `owner_manager`, `admin`, `procurement_manager` and
  rejects `viewer`, `clerk`, `supplier`, empty role (403).
- A protected write route returns 401 over HTTP when auth mode is firebase.
- A `READY_FOR_REVIEW` recommendation cannot execute (409) and creates no PO.
- A `REJECTED` recommendation cannot execute (409).
- A `REJECTED` recommendation cannot be re-decided into `APPROVED` (409).
- Duplicate execution returns the same PO id and creates exactly one PO.
- Only R4 recommendations may create purchase orders.
- `MODIFIED` merges changes over the original action, preserving untouched
  fields, and emits an audit event carrying the decision, modified action and reason.
- PO-creation audit events carry actor and timestamp.
- Approval persists reviewer identity, decision time and reason.

### Authentication scope limit

Live-browser and API validation ran with `AUTH_MODE=demo`, which grants
`owner_manager` to every caller without a credential. That is a development-only
profile. **Production Firebase Authentication — real token issuance, custom-claim
role propagation and Firestore rule enforcement — was not executed locally** and
is an integration-environment validation item.

## Automated frontend tests

Command:

```bash
cd frontend
npm ci
npm run test -- --run
```

Result:

```text
Test Files  3 passed (3)
     Tests  51 passed (51)
  Duration  30.47s
```

| File | Tests | Covers |
|---|---|---|
| `src/api.test.js` | 10 | API client success/failure, headers, error detail propagation, network failure, CSV upload |
| `src/components/Badge.test.js` | 14 | Risk, approval-status and reconciliation-outcome display tones |
| `src/App.test.js` | 27 | Dashboard, supplier list/scorecard, R4 rendering (confidence/risk/status), approve, reject, execute gating, R5 MATCH/MISMATCH, R5 review-action approval vs direct clean close, imports and audit, empty and error states |

The suite was mutation-checked: removing the `['APPROVED','MODIFIED']` guard on
the "Create purchase order" control caused 2 tests to fail, confirming the
approval gate is genuinely covered rather than incidentally passing.

## Production frontend build

```bash
cd frontend
npm run build
```

Result: success in 4.04s, 40 modules transformed, no unresolved imports.

## Live FastAPI acceptance

The FastAPI server was started locally and called over HTTP. Verified:

- `GET /api/v1/health` → 200, scope `Procurement R1-R5`.
- `GET /api/v1/agents/status` → exactly R1, R2, R3, R4, R5.
- `POST /api/v1/procurement/recommend/SKU-100` → R4 `PurchaseRecommendation`, `READY_FOR_REVIEW`, human approval required.
- The selected sample-data supplier was `SUP-002`; expected order value was R4,914.00. Cheaper but riskier alternatives remained visible rather than being silently selected.
- `POST /api/v1/procurement/reconcile/PO-DEMO-001` → `MATCH`, LOW risk, no exception.
- `POST /api/v1/procurement/reconcile/PO-DEMO-002` → `MISMATCH`, HIGH risk, detecting under-delivery, invoice/receipt quantity mismatch, price variance, defective goods and late delivery.

## Full lifecycle HTTP test

A second live API run completed the whole lifecycle:

1. Generate R4 recommendation.
2. Manager approve recommendation.
3. Explicitly execute approved recommendation to create PO.
4. Add goods receipt.
5. Add supplier invoice.
6. Run R5 three-way match.
7. Close PO.
8. Write supplier-performance feedback record for future R2/R3 scoring.

Observed final state:

- R4 initial state: `READY_FOR_REVIEW`
- Approval state: `APPROVED`
- Purchase order created: `OPEN`
- R5 result: `MATCH` / `APPROVED`
- Purchase order final state: `CLOSED`
- Supplier performance record created successfully

## Live browser regression

Backend (`uvicorn`, port 8000) and frontend (`vite`, port 5173) were started
locally and driven through a browser. All eight steps passed:

| Step | Observed |
|---|---|
| Dashboard | 3 active suppliers, 2 open POs, 0 exceptions, R 6 594,00 |
| Supplier intelligence | R2 Ubuntu Wholesale 91% (on-time 79%, fill 100%, defect 0%, confidence 58%); R3 MEDIUM, expected 5 days, P90 5.7 days, delay 25%, sample 4 |
| R4 recommendation | `REC-45ebc9cc4d5f4822`, LOW, READY_FOR_REVIEW, SUP-002, qty 260, R 4 914,00, 84% confidence; no execute control shown |
| Approval | Status → APPROVED; execute control appears |
| PO creation | `PO-B596BC8C30` created; recommendation → EXECUTED |
| R5 clean | PO-DEMO-001 → MATCH, no exceptions, variance R 0,00 |
| R5 mismatch | PO-DEMO-002 → MISMATCH; UNDER_DELIVERY, INVOICE_RECEIPT_QTY_MISMATCH, PRICE_VARIANCE, DEFECTIVE_GOODS, LATE_DELIVERY; variance R 60,00; requires explicit acceptance |
| Audit | 5 governance events, each with actor `demo:manager@example.com` and timestamp |

## Docker — PASSED, EXECUTION VALIDATED

Tooling: Docker 29.5.3 (build d1c06ef), Docker Compose v5.1.4, Docker Desktop daemon running.

| Step | Result |
|---|---|
| `docker compose config` | Valid; build context resolves to the project root |
| Backend image build | **PASSED** — `procurement-backend:local`, 188.7s, 997 MB |
| Frontend image build | **PASSED** — `procurement-frontend:local`, 33.6s, 74.1 MB |
| `docker compose up -d --build` | **PASSED** — both services created and started |
| `docker compose ps` | backend and frontend both `running`; 8000→8000, 5173→80 |
| Container logs | Clean. Uvicorn "Application startup complete"; nginx serving 200s. No import errors, no restart loops, no missing-variable warnings |
| `docker compose down` | **PASSED** — containers and network removed, nothing left running |

### Containerized runtime acceptance

| Check | Result |
|---|---|
| `GET /api/v1/health` | 200, scope `Procurement R1-R5` |
| `GET /api/v1/ready` | 200, `repository=memory`, `suppliers=3` — confirms `sample_data` resolved correctly inside the image |
| `GET /api/v1/agents/status` | 200, R1–R5 present |
| `GET /openapi.json` | 200, OpenAPI 3.1.0 |
| Frontend `GET /` | 200 from nginx |
| Frontend → backend | **PASSED** — dashboard rendered live backend data in the browser |

### Containerized procurement smoke workflow

| Step | Observed |
|---|---|
| Supplier intelligence | R2 0.9134, on-time 0.7921; R3 MEDIUM, expected 5.0d, P90 5.7d |
| R4 recommendation | `REC-b8edb3fdc6b44fa3`, READY_FOR_REVIEW, LOW, SUP-002, qty 260, confidence 0.837 |
| Execute before approval | **HTTP 409 — correctly blocked** |
| Approval | APPROVED, reviewer and timestamp recorded |
| PO creation | `PO-143A34962D`, status OPEN |
| Duplicate execution | Same PO id returned — idempotent |
| R5 clean | PO-DEMO-001 → MATCH, variance 0.0 |
| R5 mismatch | PO-DEMO-002 → MISMATCH, variance 60.0, 5 exception types |

### Docker defects found and fixed

1. **No `.dockerignore` existed.** The build context included `backend/.venv`
   (520 MB) and `frontend/node_modules` (218 MB). Beyond slow builds, the
   frontend Dockerfile's `COPY frontend/. .` runs *after* `npm ci` and would
   have overwritten the container's Linux dependency tree with Windows host
   binaries, breaking the in-container Vite build. Added `.dockerignore`.
2. **`RUN npm ci || npm install`** silently fell back when the lockfile was
   unusable, producing non-reproducible images. Now `RUN npm ci`.

Two build warnings remain and are **not** defects: BuildKit's
`SecretsUsedInArgOrEnv` heuristic flags the `VITE_AUTH_MODE` ARG/ENV because the
name contains "AUTH". It is a mode selector (`demo` / `firebase`), not a secret.

## Firebase — PASSED, LOCAL EMULATOR VALIDATED

Tooling: firebase-tools 15.29.0, Java 21 (Temurin) inside the emulator container.

### How the emulators were run

The Firestore emulator could not start on the Windows host: the JVM failed with
`java.net.SocketException: Invalid argument: connect` from
`sun.nio.ch.UnixDomainSockets`, so Netty could not open a selector
("Unable to establish loopback connection"). This is a host JVM/AF_UNIX
restriction, not a project defect, and `-Djava.net.preferIPv4Stack=true` did not
resolve it. The suite was therefore run on Linux via
`firebase/Dockerfile.emulators`. No real project and no credentials were used —
the demo project id `demo-retail-procurement` was used throughout.

Emulators started: **Authentication 9099, Firestore 8080, Storage 9199** (hub 4400).

### Results — 68 emulator tests, all passing

| Area | Tests | Result |
|---|---|---|
| Firestore repository adapter | 19 | **PASSED** |
| Firestore security rules | 24 | **PASSED** |
| Firebase Auth emulator | 6 | **PASSED** |
| Governance under Firebase auth | 4 | **PASSED** |
| Lifecycle persisted in Firestore | 2 | **PASSED** |
| Storage emulator | 5 | **PASSED** |
| Malformed-document resilience | 2 | **PASSED** |
| Shared-architecture e2e trace + idempotency + R5 review | 3 | **PASSED** |
| Failure behavior | 3 | **PASSED** |

**Firestore adapter** — create, read, update, list, delete exercised across
`suppliers`, `supplier_quotes`, `supplier_performance`, `agent_recommendations`,
`approval_log`, `purchase_orders`, `goods_receipts`, `invoices`,
`system_events`, `agent_outputs`, `agent_state`, `agent_runs`, `outcomes`;
`insert_if_absent` append-only and atomic `write_batch`; plus query by a non-id
field, `merge=True` preserving untouched
fields, missing-document returning `None`, missing-key raising, and data
surviving a reconnection through a second adapter instance.

**Security rules** (exercised over the Firestore REST API, because the Admin SDK
deliberately bypasses rules):

| Rule under test | Result |
|---|---|
| Unauthenticated read denied | PASSED |
| Unauthenticated write denied | PASSED |
| Signed-in user with no role claim denied | PASSED |
| `role=viewer` denied | PASSED |
| `role=owner_manager` allowed to write then read back (operational data) | PASSED |
| `system_events`, `approval_log`, `agent_recommendations`, `agent_outputs`, `agent_state`, `agent_runs`, `outcomes` protected from `role=viewer` | PASSED |
| Same seven collections reject a **manager's** direct write — backend-only | PASSED — 7 tests |
| Same seven readable by a manager | PASSED — 7 tests |
| `products`, `inventory_snapshots`, `inventory_movements` read-only | PASSED — 3 tests |
| Unlisted collection denied by default (no catch-all) | PASSED |

**Firebase Auth** — `AUTH_MODE=firebase` verified against emulator-issued tokens:
a real ID token is accepted and its `role` custom claim propagates; missing,
malformed and non-bearer credentials are rejected 401; and `X-Demo-User` is
ignored, so the demo bypass is unreachable in firebase mode.

**Governance under real Firebase auth** — all seven required checks passed:
unauthenticated caller blocked (401); `role=viewer` cannot approve (403);
manager can approve; execution before approval blocked (409); rejected
recommendation cannot execute (409); approved recommendation creates exactly one
PO; duplicate execution returns the same PO id.

**Lifecycle in Firestore** — after recommend → approve → execute, the
recommendation (`status=EXECUTED`, with `reviewed_by` and `reviewed_at`), the
purchase order, the approval journal entry and the audit events were all read
back directly from Firestore, every audit event carrying actor and timestamp.
R5 MATCH and MISMATCH results were likewise persisted.

**Storage** — Storage *is* used: `services/storage.py::archive_import` uploads
CSV import evidence when `FIREBASE_STORAGE_BUCKET` is set. Verified against the
emulator: upload succeeds and returns a `gs://` URI; the object round-trips
byte-identically; `sha256` and `actor_id` metadata are preserved; unauthenticated
access and cross-user folder access are denied by `storage.rules`. The
no-bucket-configured path still returns checksum-only metadata with no upload.

### Firebase defect found and fixed

**The Firestore adapter, the auth verifier and the storage archiver each
independently called `credentials.ApplicationDefault()`**, which raises
`DefaultCredentialsError` whenever no service account is present — including
against every emulator. Local and CI emulator use was impossible. Replaced with a
shared `app/core/firebase_app.py::ensure_firebase_app()` that selects an
anonymous credential when an emulator host is configured and Application Default
/ certificate credentials otherwise. This was found by execution, not inspection.

### Known characteristic, not changed

`Settings` evaluates its `os.getenv(...)` field defaults at **module import**, so
`REPOSITORY_BACKEND` and friends must be set before the process starts. That is
true in Docker and Cloud Run, so the deployed path is unaffected, but runtime
reconfiguration is not possible and tests must inject the repository explicitly.
Left as-is deliberately: changing configuration loading is a wider refactor than
this validation pass should carry.

## R1 malformed-record handling — FOUND → FIXED → REGRESSION VERIFIED

### Found

`r1_supplier_comparator.py` read `supplier["supplier_id"]` and
`supplier["name"]` directly, and coerced quote numerics with bare `float(...)`.
The store enforces no schema, so a single incomplete document raised
`KeyError`/`ValueError` and failed the whole comparison with **HTTP 500** — taking
down supplier comparison, and with it R4, for every product. Reachable by any
privileged direct write that bypasses the API's Pydantic validation. Surfaced
during emulator testing when a fixture wrote a schema-less document.

### Fixed

Records are now screened against their existing contract models
(`Supplier`, `SupplierQuote`) before use, via
`app/services/data_quality.py::screen_records`. This reuses the definition of
"valid" that the CSV importer already applies, rather than introducing a second
set of hand-written rules that could drift.

Design points that matter:

- **Valid records are returned unchanged**, so scoring sees exactly the values it
  saw before screening existed. Ranking is bit-for-bit unaffected — asserted by
  test.
- **Blank strings are treated as absent.** One rule covers both needs: an empty
  optional such as `available_qty` stays tolerated as "unknown", while a blank
  identity field such as `supplier_id` correctly fails validation.
- **Nothing is broadly swallowed.** There is no catch-all `except`; validation is
  explicit and each rejection carries a reason.
- **Reasons never include the offending value** — only field location and
  message — so operational data cannot leak into a rationale or audit note.

Behavior now:

| Situation | Result |
|---|---|
| Valid records | Rank normally; ordering and scores unchanged |
| Some records malformed | Valid suppliers still rank; malformed ones excluded and reported |
| All records malformed | Safe `DRAFT`, empty ranking, confidence 0.0, `insufficient_evidence` — no fabricated selection |
| Diagnostics | Guardrails `malformed_suppliers_excluded:{n}` / `malformed_quotes_excluded:{n}`, plus a rationale line naming each excluded record and why |

### Regression verified

**19 focused tests** in `backend/tests/test_r1_malformed_records.py`, plus **2
emulator-backed tests** in `test_firebase_emulator.py` covering the Firestore path
where the defect originally surfaced.

Mutation-checked: reverting the supplier screening made **13 of the 19 fail**,
including the HTTP-500 case, confirming the tests genuinely bind the fix.

Live regression against **Firestore** (not the in-memory repository): four
malformed documents were written directly into the emulator, bypassing the API.
The dashboard rendered, and R4 returned an identical recommendation to the
clean-data run — SUP-002, 260 units, R 4 914,00, 84% confidence. R1 reported:

```
guardrails: malformed_suppliers_excluded:4
rationale : 4 supplier record(s) failed schema validation and were excluded:
            <no supplier_id> (supplier_id: Field required);
            SUP-LIVE-NONAME (name: Field required);
            SUP-LIVE-BADSTATUS (status: Input should be 'ACTIVE', 'SUSPENDED' or 'INACTIVE');
            SUP-LIVE-BADTERMS (payment_terms_days: Input should be a valid integer, ...)
```

The temporary malformed documents were then removed and R1 returned to three
ranked suppliers with no guardrails.

## Staging status

The repository is **staging-deployment ready**, not already deployed, and no
deployment was performed or triggered during this validation. `deploy-staging.yml`
is `workflow_dispatch` only and never fires automatically. Actual Firebase/Google
Cloud staging requires the project owner's Firebase/GCP project, authentication
configuration and GitHub secrets. The exact checklist is in `STAGING_DEPLOYMENT.md`.
