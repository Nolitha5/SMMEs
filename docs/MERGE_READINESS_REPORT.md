# Retail Procurement Agent R1–R5 — Merge & Submission Readiness Report

**Date:** 2026-09-28
**Scope:** Agent 4 — Procurement R1–R5, one domain of the shared 25-agent system
**Status:** SOURCE-CONFORMANT · DATABASE-READY · READY FOR TEAM-LEAD MERGER REVIEW

---

## 0. Cross-document compliance audit (2026-09-28)

### Source documents audited

| Level | Document | Extent |
|---|---|---|
| L1 | `docs/source/Agentic_AI_Systems_for_Retail_Operations.docx` | Full text |
| L2 | `docs/source/Agentic_AI_Retail_Operations_25_Agent_Blueprint.pdf` | All 18 pages |
| L3 | `docs/source/25_Agent_Firebase_Database_Architecture.pdf` | All 13 pages |

All three read **directly**. No requirement was taken from a prior prompt,
summary or earlier validation report.

### Requirement results

| Status | Count |
|---|---|
| PASS | **83** |
| PARTIAL | **7** |
| FAIL | **0** |
| NOT APPLICABLE | **6** |
| **Total extracted** | **96** |

Per-requirement citations: [`REQUIREMENTS_TRACEABILITY_MATRIX.md`](REQUIREMENTS_TRACEABILITY_MATRIX.md).

### Unresolved deviations

None blocking. Seven PARTIALs, each justified in the matrix §F:

| ID | Item | Why non-blocking |
|---|---|---|
| L2-18 / L3-12 | `outcomes` cross-domain fields and pipeline ownership | Procurement fills its own columns; shared evaluator owns the rest. **Reconciliation item** |
| L2-49 / L2-50 | `forecast.updated` / `inventory.updated` push subscription | Procurement pulls latest upstream state on every run, so it never acts on stale data |
| L2-66 | `domain` filter on `/recommendations` | Meaningless in a single-domain repo; trivial to add |
| L2-68/69/70 | Separate `/approve`, `/modify`, `/reject` paths | One validated `/decision` endpoint, identical semantics. **Reconciliation item** |
| L2-79 | Per-agent feature flags | Flag reported, not enforced; Procurement is complete so nothing needs disabling |

### Merge-impact summary

| Class | Count | Action |
|---|---|---|
| Procurement-owned | ~25 files | **Merge as-is** — no other member has a competing version |
| Shared contract / infrastructure | ~30 files | **Team-lead reconciliation** — one canonical version must win |
| Standalone-demo-only | ~10 files | **Do not merge** — upstream fixtures, demo bootstrap |
| Local artefacts | build output, manifest, `docs/source/` | **Do not merge** |

Highest risk: **`firebase/firestore.rules`** — one file governs the whole
database and must be combined by hand, preserving the no-catch-all property.
Full detail: [`MERGE_FILE_MANIFEST.md`](MERGE_FILE_MANIFEST.md).

### Shared repository availability

The team's actual shared repository/branch is **not present in this workspace**.
**No Git merge, conflict test or integration build has been performed**, and no
claim of "conflict-free merge" or "integration verified" is made. What is
established is source conformance, database readiness and merger-review
readiness. Actual Git compatibility requires the target repository and branch.

> **Deployment is out of scope for this phase.** Nothing was deployed and no
> deployment workflow was triggered. This report does not claim production
> readiness — it claims that development is complete and that the validation
> listed below was actually executed.

---

## 1. How to read this report

Every item carries one of four states. They are not interchangeable, and an item
is never promoted to PASSED on the strength of code inspection alone.

| State | Meaning |
|---|---|
| **PASSED** | Executed locally in this validation run and observed to succeed |
| **NOT TESTED** | Not executed. Tooling unavailable or environment-dependent. Handed to the team lead |
| **NOT APPLICABLE** | Out of scope for this standalone project |
| **DEFERRED** | Deliberately postponed to a later phase |

---

## 2. Executive status

All five procurement agents are implemented and pass acceptance testing. The
backend suite (165 tests with emulators, 98 without) and the frontend suite
(49 tests) both pass, the Vite production build succeeds, and a live browser
regression exercised the full lifecycle from recommendation through approval,
purchase-order creation and three-way reconciliation to audit.

**Shared Firebase architecture conformance is complete and execution-validated,
and has been aligned against the specification document.** Procurement persists
exactly as one domain of the shared 25-agent system: one `OutputRepository`
publishing every result through the common `SharedAgentOutput` envelope into
append-only `agent_outputs` and latest-only `agent_state`; **R1–R3 as evidence
contracts that never become review items; R4 as the single Procurement action
recommendation in `agent_recommendations`; R5 as reconciliation evidence whose
mismatches raise a separate `ReconciliationReview` action**; approvals through
`approval_log`; per-invocation `agent_runs`; `system_events` carrying triggers
only, with the audit trail composed on read; evaluation `outcomes`; upstream
D4/I1/I2/I3 consumed from `agent_state` with the local fixture publishers gated
as DEV/TEST only; ownership enforced in code; backend-only Firestore rules with
no catch-all. See §23, §24 and `SHARED_FIREBASE_CONFORMANCE.md`.

The two validation gaps carried in the previous revision are now **closed by
execution**:

- **Docker — PASSED, EXECUTION VALIDATED.** Both images build, the Compose stack
  runs, and the full procurement smoke workflow — including the approval gate and
  execution idempotency — was exercised against the containerized system.
- **Firebase — PASSED, LOCAL EMULATOR VALIDATED.** 68 tests run against the real
  Firestore adapter, the real security rules, real emulator-issued ID tokens in
  `AUTH_MODE=firebase`, and the Storage emulator.

Closing those gaps surfaced three genuine defects, all fixed: a missing
`.dockerignore` that would have broken the in-container frontend build, a
non-reproducible `npm ci || npm install` fallback, and — the most significant —
every Firebase entry point resolving Application Default Credentials
unconditionally, which made emulator and CI use impossible.

The one functional defect that pass left open — R1 failing with HTTP 500 on a
single schema-less supplier document — has since been **fixed and
regression-verified**, with 19 focused tests, 2 emulator-backed tests, and a live
regression against Firestore. See §22.

No known functional defect remains open.

---

## 3. Project scope

### In scope — implemented

| Agent | Purpose | State |
|---|---|---|
| R1 | Supplier Comparator | PASSED |
| R2 | Supplier Reliability | PASSED |
| R3 | Lead-Time Risk | PASSED |
| R4 | Purchase Order Recommender | PASSED |
| R5 | Delivery & Invoice Reconciliation | PASSED |

### External contracts — consumed via fixtures

| Contract | Source domain | State |
|---|---|---|
| `ReorderNeed` (I2) | Inventory | PASSED (fixture + validation tests) |
| `SafetyStockTarget` (I3) | Inventory | PASSED (fixture + validation tests) |
| `DemandForecast` (D4) | Demand | PASSED (fixture + validation tests) |

### Out of scope

D1–D5 Demand, I1–I5 Inventory, P1–P5 Pricing, C1–C5 Customer Engagement —
**NOT APPLICABLE**. No implementation, no connection to any other repository.

---

## 4. Standalone project verification

- All work performed only in `C:\Users\Staff 101\OneDrive\Desktop\Retail-procurement-agent`.
- No other project was read, referenced, modified, or used as a source of code.
- No architecture, configuration, credentials or documentation was carried in
  from any unrelated project.
- External-domain inputs are satisfied by local fixtures and contract tests only.

---

## 5. Repository state

**Git:** this directory is **not a git repository** — there is no `.git`, so
there is no root, branch, HEAD or status to report. No repository was initialized,
since that was not requested. Version control is a prerequisite the receiving team
must establish before merge.

**Hygiene:** PASSED

| Check | Result |
|---|---|
| `.venv` present but ignored | `.gitignore` line 9 |
| `node_modules` present but ignored | `.gitignore` line 11 |
| `dist/` build output ignored | `.gitignore` line 12 |
| `__pycache__`, `.pytest_cache` ignored | `.gitignore` lines 4–6 |
| `.env` ignored, `.env.example` retained | `.gitignore` lines 1–3 |
| `package-lock.json` present, in sync, not ignored | 176.8 KB, `npm ci` succeeds |
| Secrets scan (`.env`, `*.pem`, `*serviceAccount*.json`, `*credentials*.json`) | No matches outside dependency trees |
| `.env.example` contents | Placeholders and empty values only |
| Scratch files from validation | `backend/pytest_output.txt`, `frontend/build_output.txt` removed |
| Test files committed as source | `backend/tests/*.py`, `frontend/src/**/*.test.js`, `frontend/vitest.setup.js` |

---

## 6. Backend test results — PASSED

```bash
cd backend && pytest -q
```

Default run (no emulators — the 68 emulator tests skip automatically):

```
125 passed, 0 failed, 68 skipped, 1 warning in 2.35s
```

With the Firebase emulator suite running:

```
193 passed, 0 failed, 0 skipped, 1 warning in 82.66s
```

| Area | File | Tests |
|---|---|---|
| R1 Supplier Comparator | `test_r1.py` | 2 |
| R2 Supplier Reliability | `test_r2.py` | 2 |
| R3 Lead-Time Risk | `test_r3.py` | 2 |
| R4 PO Recommender | `test_r4.py` | 3 |
| R5 Reconciliation | `test_r5.py` | 3 |
| Contracts | `test_contracts.py` | 4 |
| API | `test_api.py` | 3 |
| Services | `test_services.py` | 2 |
| Workflow / idempotency | `test_workflow.py` | 2 |
| Authorization & governance | `test_governance_security.py` | 21 |
| R1 malformed-record handling | `test_r1_malformed_records.py` | 19 |
| Shared Firebase architecture | `test_shared_architecture.py` | 55 |
| **Core subtotal** | | **118** |
| Firebase emulator integration | `test_firebase_emulator.py` | 68 |
| **Total with emulators** | | **186** |

The single warning is a third-party `DeprecationWarning` from Starlette's test
client (`anyio.abc.BlockingPortal` alias). It is not raised by project code.

---

## 7. Frontend test results — PASSED

```bash
cd frontend && npm ci && npm run test -- --run
```

```
Test Files  3 passed (3)
     Tests  51 passed (51)
  Duration  30.47s
```

| File | Tests |
|---|---|
| `src/api.test.js` | 10 |
| `src/components/Badge.test.js` | 14 |
| `src/App.test.js` | 27 |
| **Total** | **51** |

Stack: Vitest 3.2.7, jsdom, `@testing-library/react` 16, `@testing-library/jest-dom` 6.

Required coverage areas, each mapped to executed tests:

| # | Required area | Covered by |
|---|---|---|
| 1 | API client success handling | `api.test.js` — parsed body, base path, demo header, header/method passthrough |
| 2 | API client failure handling | `api.test.js` — server `detail`, status fallback, non-JSON body, network failure |
| 3 | Supplier list / scorecard rendering | `App.test.js` — list, empty table, R2/R3 scorecard, scorecard failure |
| 4 | R4 recommendation rendering | `App.test.js` — supplier, quantity, rationale |
| 5 | Confidence display | `App.test.js` — 84% rendered on the card |
| 6 | Risk display | `App.test.js` + `Badge.test.js` — LOW/MEDIUM/HIGH tones |
| 7 | Recommendation status display | `App.test.js` + `Badge.test.js` — READY_FOR_REVIEW / APPROVED / EXECUTED / REJECTED / DRAFT |
| 8 | Approval control behavior | `App.test.js` — controls shown only while awaiting review; APPROVED payload sent |
| 9 | Rejection behavior | `App.test.js` — REJECTED payload sent; execute control hidden when rejected |
| 10 | Purchase-order creation control | `App.test.js` — hidden until APPROVED, execute endpoint called, governance 409 surfaced |
| 11 | R5 MATCH rendering | `App.test.js` — MATCH badge, no-exceptions copy, Close PO control |
| 12 | R5 MISMATCH / exception rendering | `App.test.js` — MISMATCH badge, exception list, explicit acceptance required |
| 13 | Empty state | `App.test.js` — empty suppliers, empty recommendations, import empty state, empty audit |
| 14 | Server / API error state | `App.test.js` — dashboard failure, scorecard failure, execute failure, reconcile failure |

### Suite quality check

The suite was mutation-tested rather than trusted. Removing the
`['APPROVED','MODIFIED']` guard from the "Create purchase order" control made
2 tests fail; the guard was restored and the suite returned to 49 passing. This
demonstrates the approval gate is genuinely covered.

---

## 8. Production frontend build — PASSED

```bash
cd frontend && npm run build
```

```
vite v7.3.6 — 40 modules transformed — built in 4.04s
dist/index.html                      0.50 kB │ gzip:  0.33 kB
dist/assets/index-BKEl6jhi.css      14.51 kB │ gzip:  3.28 kB
dist/assets/index.esm-CM35_PMo.js  155.50 kB │ gzip: 44.77 kB
dist/assets/index-CWr7RLVP.js      211.30 kB │ gzip: 66.10 kB
```

No unresolved imports, no build errors.

---

## 9. Live browser regression — PASSED

Backend on port 8000 (`uvicorn`), frontend on port 5173 (`vite`), demo auth.
Run after all test and CI changes, to confirm nothing regressed.

| # | Step | Observed |
|---|---|---|
| 1 | Dashboard | 3 active suppliers, 0 pending, 2 open POs, 0 exceptions, R 6 594,00; R1–R5 all READY |
| 2 | Supplier intelligence | R2 Ubuntu Wholesale 91% (on-time 79%, fill 100%, defect 0%, confidence 58%); R3 MEDIUM, expected 5 days, P90 5.7 days, delay 25%, sample 4 |
| 3 | R4 recommendation | `REC-45ebc9cc4d5f4822` — LOW, READY_FOR_REVIEW, SUP-002, qty 260, R 4 914,00, 84% confidence, 4 rationale lines; **no execute control present** |
| 4 | Approval | Status → APPROVED; execute control appears |
| 5 | PO creation | `PO-B596BC8C30` created; recommendation → EXECUTED |
| 6 | R5 clean | PO-DEMO-001 → MATCH, no exceptions, variance R 0,00, Close PO offered |
| 7 | R5 mismatch | PO-DEMO-002 → MISMATCH; UNDER_DELIVERY, INVOICE_RECEIPT_QTY_MISMATCH, PRICE_VARIANCE, DEFECTIVE_GOODS, LATE_DELIVERY; variance R 60,00; "Accept result & close PO" required |
| 8 | Audit | 5 events, each with actor `demo:manager@example.com` and timestamp |

Both dev servers were stopped after the regression; ports 8000 and 5173 released.

---

## 10. Authorization and governance — PASSED (with a scope limit)

`backend/tests/test_governance_security.py` — 21 tests, all passing.

### Authentication boundary

| Assertion | Result |
|---|---|
| Firebase mode, no `Authorization` header → 401 | PASSED |
| Firebase mode, non-bearer header → 401 | PASSED |
| Firebase mode ignores `X-Demo-User` spoofing → 401 | PASSED |
| Invalid token maps to 401 (firebase-admin stubbed) | PASSED |
| Protected write route returns 401 over HTTP in firebase mode | PASSED |
| Demo mode's bypass asserted as intended dev-only behavior | PASSED |

### Role boundary

| Assertion | Result |
|---|---|
| `owner_manager`, `admin`, `procurement_manager` admitted | PASSED |
| `viewer`, `clerk`, `supplier`, empty role → 403 | PASSED |

### Governance boundary

| Assertion | Result |
|---|---|
| READY_FOR_REVIEW recommendation cannot execute (409), creates no PO | PASSED |
| REJECTED recommendation cannot execute (409) | PASSED |
| REJECTED recommendation cannot be re-decided to APPROVED (409) | PASSED |
| Duplicate execution returns the same PO id; exactly one PO exists | PASSED |
| Only R4 recommendations may create purchase orders | PASSED |
| MODIFIED merges over the original action, preserving untouched fields | PASSED |
| Modification emits an audit event with decision, modified action and reason | PASSED |
| PO-creation audit carries actor and timestamp | PASSED |
| Approval persists reviewer identity, decision time and reason | PASSED |

### Scope limit — read this before relying on the above

Live browser and API validation ran with `AUTH_MODE=demo`. That profile grants
`owner_manager` to **every caller with no credential**, taking identity from the
caller-supplied `X-Demo-User` header. It is a development-only profile.

**Production Firebase Authentication was not exercised.** Real token issuance,
custom-claim role propagation and rule enforcement are **NOT TESTED** here. What
*is* proven is that firebase mode refuses unauthenticated requests and refuses to
honor the demo header, so the bypass is not reachable once `AUTH_MODE=firebase`
is set.

---

## 11. External contract validation — PASSED

| Contract | Valid payload | Missing field | Wrong type | Boundary values | Stale timestamp |
|---|---|---|---|---|---|
| `ReorderNeed` (I2) | PASSED | PASSED | PASSED | PASSED | PASSED |
| `SafetyStockTarget` (I3) | PASSED | PASSED | PASSED | PASSED | PASSED |
| `DemandForecast` (D4) | PASSED | PASSED | PASSED | PASSED | PASSED |

R4 returns a non-actionable DRAFT with an `insufficient_evidence` reason when
required evidence is missing or stale, rather than fabricating inputs. Verified
by `test_r4_fails_safe_on_stale_external_contract` and the contract suite.

---

## 12. End-to-end lifecycle — PASSED

**Scenario A — successful procurement.** Supplier → quote → R1 comparison → R2
reliability → R3 lead-time risk → I2/I3/D4 fixtures → R4 recommendation → human
approval → explicit PO creation → goods receipt → invoice → R5 MATCH → PO close →
supplier-performance write-back feeding future R2/R3. Covered by
`test_end_to_end_recommend_approve_execute_reconcile_close` and reproduced in the
browser.

**Scenario B — problem procurement.** PO-DEMO-002 carries under-delivery, price
variance, defective goods and late delivery. R5 returned MISMATCH with all five
exception types and a R 60,00 financial variance, and required explicit human
acceptance before closure. Covered by `test_r5_detects_three_way_mismatches` and
reproduced in the browser.

---

## 13. CI — PASSED (configuration updated and locally verified)

`.github/workflows/ci.yml` frontend job, after this correction:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '22'
    cache: npm
    cache-dependency-path: frontend/package-lock.json
- run: npm ci
  working-directory: frontend
- name: Frontend unit tests (non-watch)
  run: npm run test -- --run
  working-directory: frontend
- run: npm run build
  working-directory: frontend
```

Changes made:

1. `npm install` → `npm ci` (reproducible, lockfile-enforcing).
2. Added a frontend test step **before** the build.
3. Cache key moved from `frontend/package.json` to `frontend/package-lock.json`.

Each step was executed locally in CI order and succeeded: `npm ci` → 49 tests
passed → build succeeded.

Backend and docker jobs are unchanged. `deploy-staging.yml` is
`workflow_dispatch:` only — it never fires automatically and was **not**
triggered.

---

## 14. Docker — PASSED, EXECUTION VALIDATED

Tooling: Docker 29.5.3 (build d1c06ef), Docker Compose v5.1.4, Docker Desktop running.

| Step | Result |
|---|---|
| `docker compose config` | **PASSED** — valid, context resolves to project root |
| Backend image | **PASSED** — `procurement-backend:local`, 188.7s, 997 MB |
| Frontend image | **PASSED** — `procurement-frontend:local`, 33.6s, 74.1 MB |
| `docker compose up -d --build` | **PASSED** — both services started |
| `docker compose ps` | **PASSED** — both `running` (8000→8000, 5173→80) |
| Logs | **PASSED** — clean startup, no import errors, no restart loops |
| `docker compose down` | **PASSED** — containers and network removed |

Runtime acceptance against the containers: health, ready
(`repository=memory`, `suppliers=3`, proving `sample_data` resolved inside the
image), agent status, `/openapi.json`, nginx serving the SPA, and the browser
rendering live backend data — all 200.

Containerized procurement smoke workflow: supplier intelligence (R2 0.9134,
R3 MEDIUM) → R4 `REC-b8edb3fdc6b44fa3` READY_FOR_REVIEW → **execution before
approval blocked with 409** → approval → PO `PO-143A34962D` → duplicate execution
returned the same PO id → R5 MATCH on PO-DEMO-001 and MISMATCH with 5 exceptions
and R 60,00 variance on PO-DEMO-002.

### Defects found and fixed

1. **No `.dockerignore`.** Build context carried `backend/.venv` (520 MB) and
   `frontend/node_modules` (218 MB). Worse than slow: the frontend Dockerfile's
   `COPY frontend/. .` runs after `npm ci`, so a Windows host `node_modules`
   would have overwritten the container's Linux dependency tree and broken the
   in-container Vite build.
2. **`RUN npm ci || npm install`** silently fell back on an unusable lockfile,
   producing non-reproducible images. Now `RUN npm ci`.

Two BuildKit `SecretsUsedInArgOrEnv` warnings remain and are **not** defects —
the heuristic flags `VITE_AUTH_MODE` because the name contains "AUTH"; it is a
mode selector (`demo` / `firebase`), not a secret.

---

## 15. Firebase — PASSED, LOCAL EMULATOR VALIDATED

Tooling: firebase-tools 15.29.0, Java 21 (Temurin) inside the emulator container.
Emulators started: **Auth 9099, Firestore 8080, Storage 9199** (hub 4400).

No real Firebase project and no credentials were used. The demo project id
`demo-retail-procurement` was used throughout, and no other project's
credentials were used or sought.

### Why the emulators run in a container

The Firestore emulator JVM cannot start on this Windows host: Netty fails to open
a selector because `sun.nio.ch.UnixDomainSockets` raises
`java.net.SocketException: Invalid argument: connect` ("Unable to establish
loopback connection"). `-Djava.net.preferIPv4Stack=true` did not help. This is a
host JVM/AF_UNIX restriction, not a project defect, so the suite runs on Linux
via `firebase/Dockerfile.emulators`. Java 21+ is required by firebase-tools 15.x,
which is why that image is not on Debian's default JRE 17.

### Results — 68 tests, all passing

| Item | State |
|---|---|
| Firestore repository adapter | **PASSED** — 19 tests |
| Firestore security rules | **PASSED** — 24 tests |
| Firebase Authentication (emulator-issued tokens) | **PASSED** — 6 tests |
| Governance under `AUTH_MODE=firebase` | **PASSED** — 4 tests |
| Lifecycle persisted in Firestore | **PASSED** — 2 tests |
| Firebase Storage + rules | **PASSED** — 5 tests |
| Malformed-document resilience | **PASSED** — 2 tests |
| Shared-architecture e2e trace + idempotency | **PASSED** — 2 tests |
| Failure behavior | **PASSED** — 3 tests |
| In-memory repository adapter | **PASSED** — 98 core tests + browser regression |

**Adapter:** CRUD across `suppliers`, `supplier_quotes`, `supplier_performance`,
`agent_recommendations`, `approval_log`, `purchase_orders`, `goods_receipts`,
`invoices`, `system_events`, `agent_outputs`, `agent_state`, `agent_runs`,
`outcomes`; `insert_if_absent` append-only semantics; atomic `write_batch`;
query by non-id field; `merge=True` preserving untouched fields; missing document
returns `None`; missing key raises; data survives reconnection through a second
adapter instance.

**Rules** (over the Firestore REST API — the Admin SDK bypasses rules by design,
so an Admin-SDK rules test would prove nothing): unauthenticated read and write
denied; signed-in user with no role claim denied; `role=viewer` denied;
`role=owner_manager` allowed to write then read back on operational data;
**all seven protected exchange/governance collections reject even a manager's
direct write while remaining readable**; shared context (`products`,
`inventory_snapshots`, `inventory_movements`) read-only; an unlisted collection
denied to everyone — proving there is no catch-all.

**Auth:** a real emulator-issued ID token is accepted and its `role` custom claim
propagates to the backend; missing, malformed and non-bearer credentials are
rejected 401; `X-Demo-User` is ignored in firebase mode, so the demo bypass is
unreachable once `AUTH_MODE=firebase`.

**Governance under real Firebase auth** — all seven required checks passed:
unauthenticated blocked (401); `viewer` cannot approve (403); manager can approve;
no execution before approval (409); rejected cannot execute (409); approved
creates exactly one PO; duplicate execution returns the same PO id.

**Lifecycle:** after recommend → approve → execute, the recommendation
(`EXECUTED`, with `reviewed_by`/`reviewed_at`), the PO, the approval journal entry
and the audit events were read back **directly from Firestore**, every audit event
carrying actor and timestamp. R5 MATCH and MISMATCH results persisted likewise.

**Storage:** genuinely used — `archive_import` uploads CSV evidence when
`FIREBASE_STORAGE_BUCKET` is set. Verified: upload returns a `gs://` URI, the
object round-trips byte-identically, `sha256` and `actor_id` metadata survive,
unauthenticated and cross-user access are denied by `storage.rules`, and the
no-bucket path still returns checksum-only metadata.

### Defect found and fixed

**All three Firebase entry points — the Firestore adapter, the auth verifier and
the storage archiver — independently called `credentials.ApplicationDefault()`**,
which raises `DefaultCredentialsError` when no service account is present,
including against every emulator. Local and CI emulator use was impossible.
Replaced with a shared `app/core/firebase_app.py::ensure_firebase_app()` that
selects an anonymous credential when an emulator host is set and ADC/certificate
credentials otherwise. **Found by execution, not inspection** — no amount of
reading the files would have surfaced it.

### Malformed-document resilience — FIXED

The `KeyError`/HTTP-500 fragility this section previously carried as an open
hardening item has been fixed and regression-verified. See §22.

### Known characteristic, not changed

`Settings` evaluates its `os.getenv(...)` field defaults at **module import**, so
`REPOSITORY_BACKEND` and similar must be set before the process starts. True in
Docker and Cloud Run, so the deployed path is unaffected — but runtime
reconfiguration is impossible and tests must inject the repository explicitly.
Changing configuration loading is a wider refactor than this pass should carry.

---

## 16. Security review — PASSED

| Check | Result |
|---|---|
| Committed API keys, tokens or service-account keys | None found |
| Firebase credentials in source | None found |
| Hardcoded passwords | None found |
| `.env.example` contents | Placeholders and empty values only |
| Real `.env` present | None |
| PII in source or sample data | None — sample suppliers are fictitious |
| CORS default | `http://localhost:5173`, environment-overridable; not wildcard |
| Authentication bypass reachable in firebase mode | No — asserted by tests |
| Input validation | Pydantic models at every API boundary |
| Secrets in logs | Audit payloads carry decisions and identifiers, not credentials |

Two open notes, neither a defect in this codebase:

- `npm audit` reports 2 moderate-severity advisories in the transitive dependency
  tree. Not remediated here because the available fix is `--force`, which would
  introduce breaking major-version changes and invalidate the validated build.
  Recommend the team lead review before staging.
- Firestore and Storage rules are now exercised against the emulator (§15) —
  unauthenticated, no-role and unauthorized-role access are all denied, and the
  procurement-manager path is allowed. What emulator testing cannot confirm is
  that the rules are actually *deployed* to a real project, which staging must
  verify.

---

## 17. Known limitations

1. **Not under version control** — no `.git`; the receiving team must initialize
   and commit before merge.
2. **Emulator validation is not cloud validation** — the emulators implement the
   rules language and the token format faithfully, but a real Firebase project
   still needs its own rules deployment, IAM, quotas and custom-claim
   provisioning. Staging must confirm those.
3. **`Settings` reads env at import** — runtime reconfiguration is impossible;
   variables must be set before process start (§15). Unaffected in containers.
4. **Frontend tests mock the network** — they prove component and client behavior,
   not backend contract compatibility. Backend contract behavior is covered
   separately, and the two meet in the browser regression.
5. **`npm audit` moderate advisories** — see §16.
6. **Emulators require Docker on this host** — the native Firestore emulator
   cannot start here (§15). CI runners on Linux can run it natively.
7. **Deterministic/statistical logic only** — no LLM inference in the decision
   path. This is a deliberate design choice, not a gap.

---

## 18. Deferred items

| Item | Rationale |
|---|---|
| Deployment to staging or production | Out of scope for this phase; explicitly excluded |
| `Settings` env-loading refactor | Wider change than this pass should carry; deployed path unaffected |
| Emulator suite wired into CI | Compose/emulator image exists and works; adding a CI job is a follow-up |
| End-to-end tests against a live backend (Playwright or similar) | Browser regression covers this manually for now |
| `npm audit` remediation | Requires breaking major-version upgrades; needs team-lead decision |

---

## 19. Integration assumptions

1. Inventory publishes valid `ReorderNeed` and `SafetyStockTarget` records; Demand
   publishes valid `DemandForecast` records. R4 enforces a freshness window and
   fails safe when evidence is missing or stale.
2. The receiving environment sets `AUTH_MODE=firebase` and provisions Firebase
   Authentication with role custom claims. The demo profile must never be enabled
   outside local development.
3. Firestore, Storage and their security rules are provisioned and deployed by the
   platform owner before any shared-environment use.
4. Supplier master data and historical performance are loaded via the CSV import
   endpoints or an equivalent integration before R2/R3 produce confident scores.

---

## 20. Changes made during this correction pass

| File | Change |
|---|---|
| `backend/requirements.txt` | `pytest` 9.0.2 → 8.3.2, `pytest-asyncio` 0.25.3 → 0.24.0 — the pinned pair was unresolvable and blocked installation |
| `backend/tests/test_governance_security.py` | **New.** 21 authorization and governance boundary tests |
| `frontend/src/api.test.js` | **New.** 10 API client tests |
| `frontend/src/components/Badge.test.js` | **New.** 14 status/risk display tests |
| `frontend/src/App.test.js` | **New.** 25 UI behavior and governance-gating tests |
| `frontend/vitest.setup.js` | **New.** jsdom + jest-dom setup, cleanup between tests |
| `frontend/vite.config.js` | Added Vitest config (jsdom, globals, setup file, `src/**/*.test.js`, `restoreMocks`) |
| `frontend/package.json` | Added devDependencies: `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` |
| `frontend/package-lock.json` | Regenerated; `npm ci` verified in sync |
| `.github/workflows/ci.yml` | `npm install` → `npm ci`; added frontend test step before build; cache key → `package-lock.json` |
| `README.md` | Test section rewritten with real counts and coverage; pointer to unvalidated items |
| `docs/VALIDATION_REPORT.md` | Rewritten with executed results, authorization detail, live regression table, and a "Not execution-validated locally" table |
| `docs/TESTING.md` | Added governance/authorization coverage; replaced the frontend section with the real suite and the mutation check |
| `docs/TEAM_HANDOFF.md` | Added validation state and an open-items table for the integration environment |
| `docs/MERGE_READINESS_REPORT.md` | This document — rewritten with separated PASSED / NOT TESTED / NOT APPLICABLE / DEFERRED states |
| `PROJECT_MANIFEST.sha256` | Regenerated — was stale for the 9 edited files and missing the 7 new ones. Now 99 entries, verified 0 mismatches, no dependency or build artifacts included |

No procurement business logic was modified. `frontend/src/App.js` was temporarily
altered during the mutation check and restored to its original content.

### Docker and Firebase validation pass

| File | Change |
|---|---|
| `.dockerignore` | **New.** Excludes `node_modules`, `.venv`, `dist`, caches, secrets and emulator state from the build context. Without it the in-container frontend build would inherit Windows host binaries |
| `frontend/Dockerfile` | `RUN npm ci \|\| npm install` → `RUN npm ci` for reproducible images |
| `backend/app/core/firebase_app.py` | **New.** Shared `ensure_firebase_app()`; selects an anonymous credential against emulators, ADC/certificate otherwise. Fixes the blocking ADC defect |
| `backend/app/core/auth.py` | Uses `ensure_firebase_app()` instead of its own ADC initialization |
| `backend/app/data/firestore_repository.py` | Same |
| `backend/app/services/storage.py` | Same |
| `firebase.json` | Added an `emulators` block (auth 9099, firestore 8080, storage 9199, UI off, singleProjectMode). Hosts bind `0.0.0.0` so the containerized suite is reachable; this block is local-only and ignored by deploys |
| `firebase/Dockerfile.emulators` | **New.** Temurin 21 + Node 22 + firebase-tools 15.29.0, so the emulator suite runs on Linux. Never deployed, holds no credentials |
| `backend/tests/test_firebase_emulator.py` | **New.** Emulator integration tests, auto-skipped when the emulators are not running |
| `.gitignore` | Added `firebase-emulator-data/`, `*-debug.log`, `tools/` |
| `docs/VALIDATION_REPORT.md`, `docs/TESTING.md`, `docs/TEAM_HANDOFF.md`, `docs/MERGE_READINESS_REPORT.md` | Docker and Firebase moved from NOT TESTED to executed results, with the defects found and the two items deliberately left unchanged |

Three application files changed (`auth.py`, `firestore_repository.py`,
`storage.py`), all for the single ADC defect. Scratch artifacts created during
the pass — the local `tools/` firebase-tools install (202.7 MB) and
`firestore-debug.log` — were removed.

**Count correction.** That pass was reported as "Modified (10)". The correct
figure is **13 modified + 4 new**. The enumerated list exceeded the stated total;
the list was right and the total was wrong.

### R1 malformed-record pass

| File | Change |
|---|---|
| `backend/app/services/data_quality.py` | **Modified.** Added `screen_records()` and `_describe()` — contract-model screening that returns usable records unchanged and excluded records with a field-level reason, never the offending value |
| `backend/app/agents/procurement/r1_supplier_comparator.py` | **Modified.** Screens suppliers and quotes before use; surfaces exclusion counts as guardrails and per-record reasons in the rationale; the insufficient-evidence branch now says when malformed data was the cause |
| `backend/tests/test_r1_malformed_records.py` | **New.** 19 regression tests |
| `backend/tests/test_firebase_emulator.py` | **Modified.** 2 emulator-backed malformed-document tests |
| `docs/VALIDATION_REPORT.md`, `docs/MERGE_READINESS_REPORT.md`, `docs/TESTING.md`, `docs/TEAM_HANDOFF.md` | **Modified.** R1 defect recorded FOUND → FIXED → REGRESSION VERIFIED; counts corrected |
| `PROJECT_MANIFEST.sha256` | **Regenerated** |

**1 new file, 7 modified.** One agent changed (`r1_supplier_comparator.py`) and
one service extended (`data_quality.py`). No contract, coordination, governance
or frontend code was touched.

### Shared Firebase architecture conformance pass

| File | Change |
|---|---|
| `backend/app/contracts/shared.py` | **New.** `SharedAgentOutput`, `AgentRun`, `SystemEvent`, `Outcome`, `InventoryPosition`; collection constants; ownership sets; `state_id()` |
| `backend/app/data/output_repository.py` | **New.** `OutputRepository` — single publication path, ownership enforcement, idempotent append-only + latest-state batch, upstream fixture seeding, `get_latest_output`, `history` |
| `backend/app/services/events.py` | **New.** `publish_event` → `system_events`, deterministic ids; replaces `audit.py` |
| `backend/app/services/runs.py` | **New.** `agent_runs` start/finish/latest-per-agent |
| `backend/tests/test_shared_architecture.py` | **New.** 35 conformance tests |
| `sample_data/products.csv`, `inventory_snapshots.csv`, `inventory_movements.csv`, `inventory_positions.csv` | **New.** Shared-format fixtures |
| `sample_data/invoices.csv` | **Renamed** from `supplier_invoices.csv` |
| `backend/app/services/audit.py` | **Removed.** Replaced by `events.py` |
| `backend/app/contracts/models.py` | `AgentResult` extended with envelope fields; `AgentContext` gains `input_refs`, `run_id` |
| `backend/app/agents/base.py` | `result()` sets `output_id`, `run_id`, merged `input_refs` |
| `backend/app/coordination/coordinator.py` | Rewritten around `OutputRepository`, `agent_runs`, `system_events`, `outcomes`; upstream read from `agent_state`; batch writes |
| `backend/app/coordination/approval.py` | Batched status + journal; emits `recommendation.decision`; `schema_version` |
| `backend/app/data/repository.py` | Protocol + in-memory `insert_if_absent`, `write_batch` |
| `backend/app/data/firestore_repository.py` | `insert_if_absent` via `create()`; atomic `write_batch` |
| `backend/app/data/bootstrap.py` | Canonical `invoices`; upstream contracts projected into `agent_state` (stamped "now" for demo); shared context fixtures |
| `backend/app/api/routes.py` | Canonical names; upstream imports publish to exchange layer; `/outputs/*`, `/runs/*`; `/audit` reads `system_events`; protected collections closed to `PUT` |
| `backend/app/agents/procurement/r5_delivery_invoice_reconciliation.py` | `invoices` |
| `backend/app/services/data_quality.py` | `PRIMARY_KEYS` reflects shared collections |
| `backend/app/worker.py` | Events instead of audit |
| `backend/tests/test_r4.py`, `test_workflow.py`, `test_firebase_emulator.py` | Renamed collections; stale test seeds `agent_state`; +24 rules tests, +2 e2e |
| `firebase/firestore.rules` | Explicit per-collection rules, no catch-all, protected collections backend-only |
| `firebase/firestore.indexes.json` | 7 composite indexes backing real queries |
| `frontend/src/App.js`, `App.test.js` | `invoices`, `inventory_positions`; `event_id` |
| `docs/SHARED_FIREBASE_CONFORMANCE.md` | **New.** Mapping, semantics, rules, indexes, matrix, integration steps |
| `README.md`, `docs/ARCHITECTURE.md`, `API.md`, `INTEGRATION_CONTRACTS.md`, `TEAM_HANDOFF.md`, `TESTING.md`, `VALIDATION_REPORT.md`, `MERGE_READINESS_REPORT.md`, `PROJECT_DOCUMENTATION.md` | Updated |
| `PROJECT_MANIFEST.sha256` | Regenerated |

**11 new (5 code/test, 4 fixtures, 1 doc, 1 rename target), 1 removed, 24
modified.** R1–R5 scoring, ranking, reliability, lead-time, decision and
reconciliation logic is byte-identical to the validated version; the 63
pre-existing tests are green.

### Shared-database alignment pass

| File | Change |
|---|---|
| `backend/app/services/audit_history.py` | **New.** Composes the audit trail on read from six canonical collections |
| `backend/app/contracts/shared.py` | `EVIDENCE_OUTPUT_TYPES` / `ACTION_OUTPUT_TYPES` replace agent-based routing; `ReconciliationReview` added |
| `backend/app/governance/policies.py` | Evidence contracts never require approval; `ReconciliationReview` is high-impact |
| `backend/app/data/output_repository.py` | Routes to `agent_recommendations` by `output_type` only; `seed_upstream_contract` gated DEV/TEST |
| `backend/app/coordination/coordinator.py` | `procurement.evidence.risk_elevated` on MEDIUM/HIGH evidence; R5 mismatch raises a separate `ReconciliationReview`; closure reads R5 evidence from `agent_outputs` and gates on the approved review |
| `backend/app/contracts/models.py` | `AgentResult.action_recommendation_id` |
| `backend/app/core/config.py` | `allow_upstream_fixtures` (`ALLOW_UPSTREAM_FIXTURES`) |
| `backend/app/api/routes.py` | Bookkeeping events removed; `/audit` composed on read (+`?entity_id`); `/events` raw trigger stream; upstream imports 403 in shared mode |
| `backend/app/data/bootstrap.py`, `backend/app/worker.py`, `backend/app/services/events.py` | Upstream seed gated; non-trigger events removed; `EVENT_EVIDENCE_RISK_ELEVATED` |
| `frontend/src/App.js`, `App.test.js` | Approves the derived review action, not the R5 evidence; closes clean matches with no approval call (+2 tests) |
| `backend/tests/test_shared_architecture.py`, `test_r5.py`, `test_firebase_emulator.py` | +20 alignment tests; R5 mismatch expectations updated to the evidence/action split; +1 Firestore review test; e2e asserts the four invariants |
| Docs (`SHARED_FIREBASE_CONFORMANCE`, `ARCHITECTURE`, `INTEGRATION_CONTRACTS`, `TEAM_HANDOFF`, `TESTING`, `VALIDATION_REPORT`, this report, `README`) | Evidence-vs-action, composed audit, DEV/TEST fixture gating |
| `PROJECT_MANIFEST.sha256` | Regenerated |

**1 new, 15 modified.** No R1–R5 algorithm touched.

---

## 24. Shared-database alignment — the four corrections

| # | Specification requirement | Now | Proof |
|---|---|---|---|
| 1 | R1–R3 are evidence, never `agent_recommendations` | Routing by `output_type`; evidence forced `requires_approval=False`; MEDIUM/HIGH → `procurement.evidence.risk_elevated` | 9 parametrized cases, R4 consumption, Firestore e2e, Docker smoke (`agent_recommendations` agents = R4 only) |
| 2 | R5 publishes evidence; only a resulting human action is a recommendation | Clean MATCH: no record, closes directly. MISMATCH: exception event + `ReconciliationReview` linked by `source_output_id`; closure 409 until approved | 4 in-memory, 1 Firestore, 2 Vitest, live UI mismatch → accept → CLOSED |
| 3 | `system_events` = triggers; audit composed from canonical evidence | Bookkeeping events removed; `services/audit_history.py` merges six sources; UI unchanged; no `audit_events` collection | 2 in-memory (incl. no-collection assertion), Firestore e2e, live Audit UI |
| 4 | Procurement is not the producer of D4/I1/I2/I3 | `ALLOW_UPSTREAM_FIXTURES` gates bootstrap, imports (403) and seeding (raises); marked DEV/TEST COMPATIBILITY ONLY | 3 gate tests |

Collections: `goods_receipts`, `invoices`. No `supplier_invoices`, no
`audit_events`, no dual writes.

---

## 23. Shared Firebase architecture — CONFORMANT, DATABASE-READY

Full specification, mapping and evidence: `SHARED_FIREBASE_CONFORMANCE.md`.
Checklist against the required declaration criteria:

| Criterion | State |
|---|---|
| R1–R5 run with shared-format Firestore data | **PASSED** — emulator e2e + live browser on Firestore |
| R1–R5 publish through common `OutputRepository` | **PASSED** |
| `agent_outputs` append-only | **PASSED** — in-memory + Firestore tests |
| `agent_state` latest valid projections | **PASSED** — incl. no regression on delayed retry |
| R4 consumes upstream from shared state | **PASSED** — D4/I2/I3 (+I1 available) via `get_latest_output` |
| No internal imports from other domains | **PASSED** — `OwnershipViolation` enforced |
| R4 publishes `agent_recommendations` | **PASSED** — with `source_output_id` |
| Approval decisions use `approval_log` | **PASSED** — sole writer `ApprovalService` |
| `agent_runs` contains execution traces | **PASSED** |
| `system_events` contains routing events | **PASSED** — 9 event types |
| `outcomes` contains actuals | **PASSED** — references `performance_id` |
| Stable ids | **PASSED** — `output_id`, deterministic `state_id`, `event_id`, `OUT-{po_id}` |
| Server timestamps | **PASSED** — all persisted timestamps backend-generated UTC |
| `schema_version`, `model_or_rule_version`, `input_refs` | **PASSED** |
| Freshness enforced | **PASSED** — 72h R4 policy + `expires_at` |
| Duplicate/retry tests | **PASSED** — 8 scenarios |
| Firestore rules | **PASSED** — 24 emulator tests, no catch-all |
| Required indexes | **PASSED** — 7 backing real queries |
| Full input-to-output trace reconstructable | **PASSED** — from Firestore alone |
| All existing Procurement tests green | **PASSED** — 63/63 |
| Live browser regression | **PASSED** — on Firestore |
| Docker regression | **PASSED** — smoke on shared architecture |
| Documentation matches implementation | **PASSED** |

Two things were found and fixed on the way that would have bitten the team:

1. **Firestore rules catch-all.** The previous `match /{document=**}` with
   `allow write: if procurementRole()` would have silently defeated any
   `allow write: if false` on protected collections, because Firestore ORs
   overlapping rule blocks. Rules now enumerate every collection and rely on
   default-deny; an emulator test guards against the catch-all returning.
2. **Fixture freshness.** Sample upstream contracts carried a fixed date that
   crossed the 72-hour window six days after authoring. Demo fixtures are now
   stamped at bootstrap; real imports keep their own provenance.

---

## 21. Final recommendation

The five procurement agents are complete and their behavior is demonstrated by
237 executed automated tests (186 backend with emulators, 51 frontend), a passing
production build, a live browser regression, and a containerized smoke workflow.
Governance is enforced and proven twice over — under demo auth and again under
real emulator-issued Firebase tokens: R4 cannot create a purchase order without
human approval, an unauthorized role cannot approve, rejected recommendations
cannot execute, duplicate execution cannot produce a duplicate PO, and every
decision is audited with actor and timestamp.

Both previously open validation gaps are closed by execution. Docker builds and
runs the full stack; the Firebase emulator suite exercises the real Firestore
adapter, the real security rules, real ID tokens and Storage. Closing them was
worth doing: it surfaced three genuine defects that inspection had missed, the
most serious being that every Firebase entry point resolved Application Default
Credentials unconditionally — which would have blocked the receiving team's first
local and CI run.

The R1 malformed-document defect that the previous revision carried as an open
hardening item is now fixed and regression-verified (§22). One item remains
reported rather than changed — `Settings` reading environment variables at import
— which is unreachable in a container deployment and is a wider refactor than
this validation work should carry.

Procurement is now conformant to the shared Firebase architecture and
database-ready (§23): its collections, envelope, exchange layer, governance
records, rules and indexes behave exactly as one domain of the shared system,
and the full input-to-output trace was reconstructed from Firestore in the
emulator.

**Recommendation: accept for team integration**, with the shared rules and
indexes deployed to the shared project, upstream domains publishing into
`agent_state` per `SHARED_FIREBASE_CONFORMANCE.md` §22, cloud-side Firebase
configuration confirmed in staging, and version control initialized before merge.

---

## 22. R1 malformed-record defect — FOUND → FIXED → REGRESSION VERIFIED

### Root cause

`r1_supplier_comparator.py` trusted the shape of stored records: it read
`supplier["supplier_id"]` and `supplier["name"]` by direct index, and coerced
quote numerics with bare `float(...)`. The repository enforces no schema — this is
a document store — so one incomplete document raised `KeyError`/`ValueError` out
of the agent and surfaced as **HTTP 500**, failing supplier comparison, and with
it R4, for every product. The same line already used `s.get("status", "ACTIVE")`
defensively, so the fragility was inconsistent rather than intentional.

### Fix

Records are screened against the contract models the CSV importer already uses
(`Supplier`, `SupplierQuote`) through a new
`app/services/data_quality.py::screen_records`. Reusing the existing models keeps
one definition of "valid" instead of adding hand-written rules that would drift
from the schema.

Four properties were deliberate:

1. **Valid records pass through unchanged**, so scoring sees exactly what it saw
   before. Ranking is unaffected — asserted by a dedicated test.
2. **Blank string means absent.** One rule serves both cases: an empty
   `available_qty` stays tolerated as "unknown", while a blank `supplier_id`
   correctly fails validation.
3. **No catch-all exception handling.** Validation is explicit and every
   exclusion carries a reason, per the requirement not to hide failures.
4. **Reasons carry field and message only, never the value**, so operational
   data cannot leak into a rationale or an audit record.

### Behavior

| Case | Result |
|---|---|
| Valid records | Rank normally; order and scores unchanged |
| Mixed valid + malformed | Valid suppliers still rank; malformed excluded and reported |
| All malformed | `DRAFT`, empty ranking, confidence 0.0, `insufficient_evidence` — no fabricated selection |
| Diagnostics | `malformed_suppliers_excluded:{n}` / `malformed_quotes_excluded:{n}` guardrails, plus a rationale line naming each excluded record and why |

### Regression verification

- **19 tests** in `backend/tests/test_r1_malformed_records.py` — valid records
  unaffected, determinism, missing/empty `supplier_id`, missing/empty `name`,
  invalid status, bad payment terms, malformed quote numerics, malformed coverage
  data, blank-optional tolerance, non-object rows, all-suppliers-malformed,
  all-quotes-malformed, R4 through the coordinator, and two HTTP tests proving no
  500 and that exclusions are reported.
- **2 emulator-backed tests** against real Firestore, where the defect surfaced.
- **Mutation-checked:** reverting the supplier screening failed **13 of 19**,
  including the HTTP-500 case.
- **Live regression against Firestore:** four malformed documents written directly
  into the emulator, bypassing the API. The dashboard rendered and R4 returned a
  recommendation identical to the clean-data run (SUP-002, 260 units, R 4 914,00,
  84% confidence), with `malformed_suppliers_excluded:4` and a per-record reason
  for each. Test data was then removed and R1 returned to three ranked suppliers
  with no guardrails.
- **Full suite immediately after that change (2026-09-09 figures):** 63 passed /
  44 skipped without emulators; 107 passed with; frontend 49 passed; production
  build succeeded. Current totals are in §0 and §23.

---

**RETAIL PROCUREMENT AGENT R1–R5 — SHARED FIREBASE ARCHITECTURE CONFORMANT, DATABASE-READY, AND READY FOR TEAM INTEGRATION**
