# Testing and Acceptance Plan

## Automated backend suite

Run:

```bash
cd backend
pytest -q
```

Coverage areas:

1. Pydantic contract validation.
2. R1 supplier ranking and no-quote fail-safe.
3. R2 good-vs-poor supplier differentiation and neutral prior.
4. R3 robust lead-time metrics and quoted fallback.
5. R4 purchase recommendation, no-reorder path and stale dependency fail-safe.
6. R5 clean match, mismatch matrix and missing evidence.
7. Recommendation approval, explicit PO execution and idempotency.
8. Full feedback loop: recommend → approve → execute → receive → invoice → reconcile → close → supplier performance.
9. HTTP health, agent status, recommendation/approval and dashboard endpoints.
10. Authorization boundaries: missing/non-bearer/invalid credentials, demo-header
    spoofing, and manager-role enforcement (`test_governance_security.py`).
11. Governance boundaries: execution blocked before approval, rejected
    recommendations blocked from execution and re-decision, duplicate execution
    yielding exactly one PO, modification auditability, and actor/timestamp on
    approval and execution audit events.

12. Malformed-record resilience: schema-less supplier and quote documents are
    screened out with reasons rather than failing the comparison
    (`test_r1_malformed_records.py`, 19 tests).

13. Shared Firebase architecture (`test_shared_architecture.py`, 62 tests):
    envelope fields, append-only `agent_outputs`, latest-only `agent_state`,
    no state regression on delayed retry, ownership violations, R1–R5 publish
    through one path, R4 upstream consumption from `agent_state` with concrete
    `input_refs`, fail-safe on absent/expired state, `agent_runs` trace with
    bounded error, `approval_log` + event idempotency, `outcomes` referencing
    `supplier_performance`, exception events, repeated close/reconcile safety,
    full trace reconstruction, and protected collections closed to `PUT /data`.
    **Evidence/action alignment:** R1/R2/R3 × LOW/MEDIUM/HIGH never create a
    recommendation but remain in outputs/state (9 parametrized cases); elevated
    risk raises `procurement.evidence.risk_elevated` instead; R4 still consumes
    them; R5 clean MATCH creates no recommendation and closes directly; R5
    MISMATCH publishes evidence, raises an exception event and a separate
    `ReconciliationReview` action; closure is refused until that action is
    approved; repeated reconciliation reuses the review for the same output.
    **Audit/events:** `system_events` holds no bookkeeping records; the audit
    history reconstructs generated → reviewed → approved → PO → reconciled →
    outcome from six canonical sources with no `audit_events` collection.
    **Dev-only upstream fixtures:** seeding, the import endpoint and bootstrap
    are each refused/skipped when `ALLOW_UPSTREAM_FIXTURES=false`.

Current result: **125 passed, 0 failed, 68 skipped** (the 68 are the Firebase
emulator tests below, which skip unless the emulators are running).

### Malformed-record regression suite

`backend/tests/test_r1_malformed_records.py` guards a fixed defect: R1 previously
indexed `supplier["supplier_id"]` and `supplier["name"]` directly and coerced
quote numerics with bare `float(...)`, so one incomplete document in a schema-less
store failed the whole comparison with HTTP 500.

| Case | Assertion |
|---|---|
| Valid records | Rank normally; ranks 1..n ordered by descending score |
| Determinism | Screening does not change order or scores |
| Missing / empty `supplier_id` | Excluded with a reason; valid suppliers still rank |
| Missing / empty `name` | Excluded with a reason |
| Invalid `status`, bad `payment_terms_days` | Excluded with a reason |
| Malformed quote numerics | Excluded; valid quotes still rank |
| Malformed coverage (`available_qty`) | Excluded, no crash |
| Blank optional value | Tolerated as "unknown", **not** excluded |
| Non-object row | Excluded, no crash |
| No KeyError | Explicit guard on the original failure mode |
| All suppliers / all quotes malformed | `DRAFT`, empty ranking, confidence 0.0, `insufficient_evidence` |
| R4 via the coordinator | Same supplier and quantity as the clean-data baseline |
| HTTP | `/procurement/recommend` returns 200, and `/agents/R1/run` reports `malformed_suppliers_excluded` |

Mutation-checked: reverting the supplier screening failed 13 of the 19 tests,
including the HTTP-500 case.

## Firebase emulator suite

`backend/tests/test_firebase_emulator.py` — 68 tests exercising the **real**
`FirestoreRepository`, the **real** `firestore.rules`, and **real**
emulator-issued ID tokens with `AUTH_MODE=firebase`. Nothing in this file uses
the in-memory repository or demo auth.

The emulators run in a container because the Firestore emulator JVM cannot start
on this Windows host (`sun.nio.ch.UnixDomainSockets` / "Unable to establish
loopback connection" — a host restriction, not a project defect):

```bash
docker build -f firebase/Dockerfile.emulators -t procurement-emulators:local .
docker run -d --name procurement-emulators \
  -p 9099:9099 -p 8080:8080 -p 9199:9199 -p 4400:4400 \
  -v "$PWD/firebase.json:/project/firebase.json:ro" \
  -v "$PWD/firebase:/project/firebase:ro" \
  procurement-emulators:local
```

Then:

```bash
cd backend
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
FIREBASE_STORAGE_EMULATOR_HOST=127.0.0.1:9199 \
FIREBASE_PROJECT_ID=demo-retail-procurement \
pytest tests/test_firebase_emulator.py -q
```

On Windows PowerShell set the same four variables with `$env:NAME = "..."` first.

| Area | Tests | Covers |
|---|---|---|
| Firestore adapter | 19 | CRUD across 13 collections (operational + exchange + governance), query by non-id field, `merge=True` preserving untouched fields, missing document, missing key, persistence across a reconnection |
| Security rules | 24 | Unauthenticated read/write denied, no-role denied, `viewer` denied, `owner_manager` allowed on operational data; **7 protected collections reject even a manager's direct write and remain readable**; shared context read-only; unlisted collection denied by default (no catch-all) |
| Shared-architecture e2e | 3 | Phase 25 trace: seed → R1–R4 → recommendation in all three places → event → approval_log → PO → receipt/invoice events → R5 → outcomes → agent_runs → trace reconstructed from persisted records, plus: no R1–R3 approval records, clean R5 raises none, `system_events` holds no bookkeeping, audit composed from six sources; same-output-twice idempotency in Firestore; R5 MISMATCH raises a linked `ReconciliationReview`, closure 409 until approved |
| Auth emulator | 6 | Valid token accepted, role claim propagated, missing/malformed/non-bearer rejected, `X-Demo-User` ignored in firebase mode |
| Governance under Firebase auth | 4 | Unauthenticated blocked, unauthorized role cannot approve, manager can approve, no execution before approval, rejected cannot execute, one PO per recommendation, idempotent re-execution |
| Lifecycle in Firestore | 2 | Recommendation/PO/approval log/audit events all read back from Firestore; R5 results persisted |
| Storage emulator | 5 | Upload with `gs://` URI, byte-identical round-trip, sha256 and actor metadata preserved, no-bucket path, rules deny unauthenticated and cross-user access |
| Malformed-document resilience | 2 | A schema-less supplier written directly to Firestore does not break R1 or R4, and is reported |
| Failure behavior | 3 | Missing document 404, unreachable Firestore raises, invalid payload 422 |

Current result: **68 passed, 0 failed, 0 skipped**. Combined with the core suite
and emulators running: **193 passed**.

Two notes on how these are written, both deliberate:

- **Rules are tested over the Firestore REST API, not the Admin SDK.** The Admin
  SDK bypasses security rules by design, so an Admin-SDK "rules test" would
  prove nothing.
- **The repository is injected via `app.dependency_overrides[repo_dep]`**, not
  via `REPOSITORY_BACKEND`. `Settings` evaluates its `os.getenv` defaults at
  module import, so setting that variable after import has no effect. Containers
  set it before the process starts, so the deployed path is unaffected.

## Minimum acceptance scenarios

### Scenario A — purchase recommendation

`SKU-100` must produce an R4 `PurchaseRecommendation` in `READY_FOR_REVIEW`, with supplier, quantity, expected cost, confidence, risk, evidence and rationale.

### Scenario B — no purchase required

`SKU-200` must return `NoPurchaseRequired` without creating a PO.

### Scenario C — clean reconciliation

`PO-DEMO-001` must return `MATCH` with no exception.

### Scenario D — exception reconciliation

`PO-DEMO-002` must detect at least under-delivery, price variance, defective goods and late delivery and place the result into human review.

### Scenario E — stale evidence

An I2/I3/D4 record older than the freshness window must cause R4 to return DRAFT with `insufficient_evidence` rather than a confident recommendation.

## Automated frontend suite

Run:

```bash
cd frontend
npm ci
npm run test -- --run
```

Vitest runs in a jsdom environment with `@testing-library/react`. `global.fetch`
is replaced by a route-matching mock, so the tests exercise the real components
and the real API client without a running backend.

| File | Tests | Coverage |
|---|---|---|
| `src/api.test.js` | 10 | Parsed success body, base path, demo identity header, caller header/method passthrough, server `detail` error propagation, status fallback, non-JSON error body, network failure, CSV upload form data, import validation failure |
| `src/components/Badge.test.js` | 14 | Risk tones (HIGH/MEDIUM/LOW), approval statuses (READY_FOR_REVIEW/APPROVED/EXECUTED/REJECTED/DRAFT), reconciliation outcomes including MISMATCH-vs-MATCH substring precedence, fallback and case-insensitivity |
| `src/App.test.js` | 25 | Dashboard KPIs and agent list, dashboard API failure, supplier list and empty table, R2/R3 scorecard, scorecard failure, R4 card rendering (supplier, qty, confidence, risk, status, rationale), empty recommendations, approve/reject control visibility, execute control hidden until APPROVED and hidden when REJECTED, decision payloads, execute call, governance rejection surfaced, PO list, R5 MATCH, R5 MISMATCH with exception list, explicit acceptance required for mismatch, reconciliation error, import empty state and disabled control, audit rendering and empty audit |

Current result: **51 passed, 0 failed, 0 skipped**.

CI runs `npm ci` → frontend tests (non-watch) → `npm run build`, in that order.

### Suite quality check

The suite is mutation-checked rather than assumed meaningful. Removing the
`['APPROVED','MODIFIED']` status guard from the "Create purchase order" control
caused 2 tests to fail; the guard was then restored. A suite that passes with the
governance gate removed would not be evidence of anything.

## Browser acceptance

Automated tests do not replace a browser pass. Local regression covers:

- Demo login (development profile)
- Dashboard metrics
- Supplier R2/R3 scorecard
- R4 generation
- Approve/reject
- PO creation only after approval
- R5 clean and exception flows
- Audit trail
- responsive layout and empty/error states

Firebase login specifically is **not** covered locally — see the authentication
scope limit in `VALIDATION_REPORT.md`. It is a staging acceptance item.
