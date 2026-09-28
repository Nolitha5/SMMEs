# Shared Firebase Architecture Conformance — Procurement (R1–R5)

**Date:** 2026-09-14
**Scope:** Agent 4 — Procurement, as one domain inside the shared 25-agent system

> **Specification note (updated 2026-09-28).** Earlier revisions of this document
> were written before the source PDFs were available and worked from the
> specification as stated in the task. All three authoritative documents have
> since been read directly from `docs/source/`, and every requirement is now
> traced to a document and page in
> [`REQUIREMENTS_TRACEABILITY_MATRIX.md`](REQUIREMENTS_TRACEABILITY_MATRIX.md).
> That audit confirmed this design and corrected five items; see §25.

---

## 1. Phase 1 — Conformance audit and mapping

The mapping below was produced **before** any change was made.

### 1.1 Collections

| Current | Classification | Target | Reason |
|---|---|---|---|
| `suppliers` | **KEEP** | `suppliers` | Canonical operational collection |
| `supplier_quotes` | **KEEP** | `supplier_quotes` | Canonical |
| `supplier_performance` | **KEEP** | `supplier_performance` | Canonical; Procurement is the operational writer |
| `purchase_orders` | **KEEP** | `purchase_orders` | Canonical |
| `goods_receipts` | **KEEP** | `goods_receipts` | Canonical |
| `supplier_invoices` | **RENAME** | `invoices` | Canonical name is `invoices`. Migrated outright rather than aliased — two permanent names for one data class is forbidden |
| `reorder_needs` | **REFACTOR** | `agent_state` (I2 `ReorderNeed`) | Upstream *published contract*, not Procurement source data. Read from the exchange layer. The CSV import remains as a local fixture loader that projects into `agent_outputs` + `agent_state` on behalf of the upstream agent |
| `safety_stock_targets` | **REFACTOR** | `agent_state` (I3 `SafetyStockTarget`) | Same |
| `demand_forecasts` | **REFACTOR** | `agent_state` (D4 `DemandForecast`) | Same |
| `agent_recommendations` | **REFACTOR** | `agent_recommendations` | Currently stores *every* agent result. Target: **action contracts only** — R4 `PurchaseRecommendation` and the R5-derived `ReconciliationReview`. Evidence (R1–R3, R5 facts) never lands here, whatever its risk tier |
| `approval_log` | **KEEP** | `approval_log` | Already matches the shared schema (`recommendation_id`, `reviewer`, `decision`, `modified_action`, `reason`, `decided_at`) |
| `audit_events` | **DEPRECATE** | *composed on read* | Not part of the canonical architecture, and `system_events` is **not** its replacement — that collection carries routing triggers only. The audit history is now built on read from `agent_runs`, `agent_outputs`, `agent_recommendations`, `approval_log`, `system_events` and `outcomes` (`services/audit_history.py`). No duplicate audit collection exists |
| `agent_status` | **DEPRECATE** | derived from `agent_runs` | A per-agent "last run" summary. Replaced by the per-execution `agent_runs` trace; the dashboard's status view is now derived from the latest run per agent |
| — | **ADD** | `agent_outputs` | Append-only immutable record of every published contract |
| — | **ADD** | `agent_state` | Latest valid projection per agent / output type / entity |
| — | **ADD** | `agent_runs` | Execution trace per run |
| — | **ADD** | `outcomes` | Actual procurement results for evaluation and R2/R3 feedback |
| — | **ADD (read-only)** | `products`, `inventory_snapshots`, `inventory_movements` | Shared operational context Procurement may read but never writes. Fixtures provided; no Procurement logic writes them |

### 1.2 Models

| Current model | Classification | Target |
|---|---|---|
| `AgentResult` | **REFACTOR (extend)** | Gains `output_id`, `domain`, `input_refs`, `run_id`, `schema_version`. Kept as the agents' working return type so every existing consumer and test continues to work; the `SharedAgentOutput` envelope is derived from it |
| — | **ADD** | `SharedAgentOutput` — the common published envelope with the exact required fields |
| — | **ADD** | `AgentRun`, `SystemEvent`, `Outcome`, `InventoryPosition` (I1 contract) |
| `AuditEvent` | **DEPRECATE** | Replaced by `SystemEvent` |
| `SupplierInvoice` | **KEEP** | Model name unchanged; only the collection it lives in is renamed |
| `ReorderNeed`, `SafetyStockTarget`, `DemandForecast` | **KEEP** | Upstream contract payload models; now carried inside `SharedAgentOutput.payload` |
| All R1–R5 payload models | **KEEP** | `SupplierComparison`, `SupplierReliabilityScore`, `LeadTimeRisk`, `PurchaseRecommendation`, `ProcurementException` — unchanged |

### 1.3 Services

| Current | Classification | Target |
|---|---|---|
| `ProcurementCoordinator._store_result` | **REFACTOR** | Delegates to `OutputRepository.publish()`; no longer writes `agent_recommendations` directly |
| `services/audit.py::record_audit` | **DEPRECATE** | Trigger-worthy calls → `services/events.py::publish_event` (`system_events`); bookkeeping calls (import, upsert, bootstrap, job completion) dropped — not triggers. Audit trail → `services/audit_history.py::build_audit_history` |
| — | **ADD** | `data/output_repository.py::OutputRepository` — the single publication path for all agents |
| — | **ADD** | `services/runs.py` — `agent_runs` trace helpers |
| `ApprovalService` | **KEEP** | Already the sole `approval_log` writer; now also emits a `system_events` record |
| `coordinator.close_purchase_order` | **REFACTOR** | Also writes an `outcomes` record referencing the `supplier_performance` row |
| `coordinator.recommend_purchase` | **REFACTOR** | Reads I2/I3/D4 via `OutputRepository.get_latest_output()` instead of private collections |

### 1.4 What is deliberately not changed

- R1–R5 scoring, ranking, reliability, lead-time, decision and reconciliation
  algorithms. Conformance is a persistence and contract concern; the business
  logic already validated stays as it is.
- The approval state machine and `can_execute` governance.
- The frontend's pages and workflows. It continues to use backend APIs only.

---

## 2. Procurement's role in the 25-agent shared system

Procurement is one domain of five. It owns supplier intelligence and the
purchase lifecycle, consumes Demand and Inventory contracts, and publishes five
contracts that Inventory and the coordinator can consume. It never imports
another domain's code, never writes another domain's outputs, and never creates
a purchase order without a human decision.

```
        Demand (D4)  ──┐                          ┌──► Inventory (consumes LeadTimeRisk,
     Inventory (I1–I3)─┤  agent_state / outputs   │      PurchaseRecommendation, in-transit)
                       ▼                          │
   suppliers ──► R1 ──► R2 ──► R3 ──► R4 ──► [human] ──► purchase_orders ──► R5 ──► outcomes
   quotes                                    approval_log                     supplier_performance
                                                                                     │
                                             system_events ◄─────────────────────────┘
```

## 3. Collections Procurement reads

| Collection | Owner | Purpose |
|---|---|---|
| `suppliers`, `supplier_quotes`, `supplier_performance`, `purchase_orders`, `goods_receipts`, `invoices` | Procurement | Operational source data |
| `products`, `inventory_snapshots`, `inventory_movements` | Inventory / shared | Read-only context |
| `agent_state` | Shared | Latest `DemandForecast` (D4), `InventoryPosition` (I1), `ReorderNeed` (I2), `SafetyStockTarget` (I3), and its own R1–R3 outputs |
| `agent_outputs` | Shared | History and trace resolution |
| `agent_recommendations`, `approval_log` | Shared governance | Approval state for execution and closure |

## 4. Collections Procurement writes

| Collection | Path | Mode |
|---|---|---|
| `agent_outputs` | `OutputRepository.publish()` only | Append-only |
| `agent_state` | `OutputRepository.publish()` only | Replace latest |
| `agent_recommendations` | `OutputRepository.publish()` (create) · `ApprovalService` / executor (status) | Create + status update |
| `approval_log` | `ApprovalService.decide()` only | Append-only |
| `agent_runs` | `services/runs.py` via the coordinator | Start + finalize |
| `system_events` | `services/events.py::publish_event` | Append-only, idempotent |
| `outcomes` | `coordinator.close_purchase_order` | Append-only |
| `purchase_orders` | `coordinator.execute_purchase_recommendation` / close | Canonical writer |
| `supplier_performance` | `coordinator.close_purchase_order` | Canonical writer |
| `suppliers`, `supplier_quotes`, `goods_receipts`, `invoices` | Import / upsert APIs | Canonical writer |

All writes above are performed by the trusted backend (Admin SDK). The frontend
calls authenticated backend APIs and never touches Firestore directly.

## 5. R1–R5 published contracts — evidence vs action

The shared architecture distinguishes two kinds of contract, and the
distinction governs where each is written:

- **Evidence contracts** are analytical outputs that inform a decision. They
  live in `agent_outputs` + `agent_state` only. They never carry approval
  semantics: an elevated risk tier raises a `system_event`, not a review item.
- **Action contracts** ask a human to approve, modify or reject something. They
  are additionally routed to `agent_recommendations`.

| Agent | `output_type` | Kind | `entity_type` | Payload model |
|---|---|---|---|---|
| R1 | `SupplierComparison` | evidence | product | `SupplierComparison` |
| R2 | `SupplierReliabilityScore` | evidence | supplier | `SupplierReliabilityScore` |
| R3 | `LeadTimeRisk` | evidence | supplier | `LeadTimeRisk` |
| R4 | `PurchaseRecommendation` | **action** | product | `PurchaseRecommendation` |
| R4 | `NoPurchaseRequired` | evidence | product | decision record; nothing to approve |
| R5 | `ProcurementException` | evidence | purchase_order | `ProcurementException` — reconciliation facts incl. `match_status` |
| R5-derived | `ReconciliationReview` | **action** | purchase_order | accept-and-close proposal, `source_output_id` → the R5 output |

**R1–R3 = evidence contracts. R4 = the Procurement action recommendation.
R5 = reconciliation/exception evidence; only a resulting human action becomes a
recommendation.**

R5 behaviour: a clean `MATCH` publishes evidence and writes outcomes/performance
at closure — no recommendation record. A `MISMATCH`/`PARTIAL_MATCH` publishes
the evidence, raises `procurement.exception.created`, and *separately* raises
one `ReconciliationReview` action that a manager must approve before the PO can
close. "R5 detected an exception" and "a human action is now recommended" are
two records linked by `source_output_id`. Closing a PO with exceptions without an
approved review is refused (409); the safety gate is unchanged, it now sits on
the action rather than the evidence.

Payload models are unchanged from the validated implementation.

## 6. Upstream contracts consumed

| Producer | `output_type` | Domain | Required by R4 |
|---|---|---|---|
| D4 | `DemandForecast` | demand | Yes |
| I2 | `ReorderNeed` | inventory | Yes |
| I3 | `SafetyStockTarget` | inventory | Yes |
| I1 | `InventoryPosition` | inventory | Available; not required by current R4 logic |

Read via `OutputRepository.get_latest_output(output_type, entity_id)`. Payloads
are validated against the contract models in `contracts/models.py` /
`contracts/shared.py`. Nothing is fabricated: absent or invalid state yields
`None`, and R4 returns a non-actionable `DRAFT` with `insufficient_evidence`.

**Procurement only reads these. It is never their producer.** In the shared
system D4 comes from Demand and I1/I2/I3 from Inventory.

### DEV/TEST COMPATIBILITY ONLY — standalone fixtures

So Procurement can run and be tested on its own, two local mechanisms publish
these contracts *on the upstream agents' behalf*:

- `bootstrap_sample_data` seeds `sample_data/{demand_forecasts,inventory_positions,reorder_needs,safety_stock_targets}.csv` into `agent_state`;
- `POST /imports/{demand_forecasts|inventory_positions|reorder_needs|safety_stock_targets}` publishes CSV rows the same way.

Both go through `OutputRepository.seed_upstream_contract()`, a deliberately
separate entry point from `publish()`, and both are gated by
`ALLOW_UPSTREAM_FIXTURES` (default `true` for development). **Shared/integration
mode must set it `false`**: bootstrap then skips the upstream seed, the import
endpoints return 403, and `seed_upstream_contract()` raises
`OwnershipViolation`. Three tests prove each gate.

## 7. Common output envelope — `SharedAgentOutput`

Defined in `backend/app/contracts/shared.py`.

| Field | Semantics |
|---|---|
| `output_id` | Unique, idempotency key. Same value as the working `recommendation_id` |
| `agent_id` | `R1`–`R5` (or `D4`/`I1`/`I2`/`I3` for seeded upstream fixtures) |
| `domain` | `procurement` |
| `output_type` | One of §5 |
| `entity_type` / `entity_id` | product, supplier or purchase_order identity |
| `payload` | Typed Procurement result (dict of the payload model) |
| `input_refs` | Concrete ids of evidence consumed — see §19 |
| `confidence` | 0–1 |
| `risk_level` | LOW / MEDIUM / HIGH |
| `generated_at` | Backend UTC timestamp |
| `expires_at` | Recommendation TTL (24h default) |
| `model_or_rule_version` | e.g. `1.0.0-r4` |
| `run_id` | Links to `agent_runs` |
| `schema_version` | `1.0` |
| `state_id` | Derived: `{agent_id}:{output_type}:{entity_id}` |

The agents' working object `AgentResult` was **extended** with these fields
rather than replaced, so every existing consumer and test kept working; the
envelope is derived from it at publication.

## 8. `agent_outputs` behavior

Append-only. `OutputRepository.publish()` uses `insert_if_absent` (Firestore
`create()`, which the server rejects if the document exists). Republishing the
same `output_id` changes nothing; republishing with different content does
**not** overwrite history — proven by `test_agent_outputs_is_append_only`.

## 9. `agent_state` behavior

One document per `state_id`, replaced on publish. A delayed retry carrying an
older `generated_at` cannot regress state — proven by
`test_delayed_retry_cannot_regress_state`. Written in the same batch as the
`agent_outputs` record so a reader never sees one without the other.

## 10. `agent_recommendations` behavior

Holds **action contracts only**: R4 `PurchaseRecommendation` and the R5-derived
`ReconciliationReview`. Routing is by `output_type` alone — never by risk tier,
never by agent identity. R1–R3 outputs and R5 evidence are never written here,
and the governance policy (`finalize_agent_result`) forces
`requires_approval=False` on every evidence contract so an agent cannot
accidentally request one. Each record carries `source_output_id`, `domain`,
`schema_version` in addition to every previously validated field. Status
transitions happen only through `ApprovalService` and the executor.

## 11. `approval_log` behavior

Written only by `ApprovalService.decide()`. Fields: `approval_id`,
`recommendation_id`, `reviewer`, `decision` (APPROVED / MODIFIED / REJECTED),
`modified_action`, `reason`, `decided_at`, `schema_version`. The status change
and the journal entry commit in one batch. Neither agents nor the frontend can
write it — enforced by code path and by Firestore rules.

## 12. `agent_runs`

Created at agent start (`RUNNING`), finalized on completion (`SUCCEEDED` /
`FAILED`). Fields: `run_id`, `agent_id`, `domain`, `entity_type`, `entity_id`,
`started_at`, `completed_at`, `status`, `duration_ms`, `model_or_rule_version`,
`schema_version`, `input_refs`, `output_id`, `actor_id`, `error` (bounded to
500 characters; never a stack trace or secret). The dashboard's agent status
view is derived from the latest run per agent — the former `agent_status`
collection is gone.

## 13. `system_events` — triggers, not an audit log

`system_events` carries routing/trigger records: something happened that
another agent, domain or the coordinator may need to react to. It is **not**
the audit log and holds no bookkeeping copies — CSV imports, upserts, demo
bootstrap and worker completion are not triggers and are not recorded here.

Fields: `event_id`, `event_type`, `producer_domain`, `producer_agent`,
`entity_type`, `entity_id`, `payload`, `actor_id`, `created_at`, `processed`,
`schema_version`. Events published:

| Event | When | Who reacts |
|---|---|---|
| `purchase.recommendation.created` | R4 issues a PurchaseRecommendation | approval queue |
| `recommendation.decision` | An approval decision is recorded | executor eligibility |
| `purchase_order.created` | Approved recommendation executed | Inventory (in-transit) |
| `goods.receipt.recorded` | Receipt imported or upserted | reconciliation eligibility |
| `invoice.received` | Invoice imported or upserted | reconciliation eligibility |
| `procurement.reconciliation.completed` | R5 ran | downstream |
| `procurement.exception.created` | R5 found exceptions | exception handling |
| `purchase_order.closed` | PO closed | Inventory |
| `supplier.performance.updated` | New performance fact written | R2/R3 re-evaluation, Inventory |
| `procurement.evidence.risk_elevated` | An R1–R3 evidence contract came back MEDIUM/HIGH | alerting — this is the signal that replaces "approving" evidence |

IDs are deterministic (`sha256(event_type|entity_id|idempotency_key)`) wherever
a natural key exists, so a retried publish is a no-op. Raw stream:
`GET /events?event_type=…`.

## 13a. Audit history — composed on read

There is no audit collection. `GET /audit` (and the Audit UI) returns a
timeline built by `services/audit_history.py` from six canonical sources:

| Source | Contributes |
|---|---|
| `agent_runs` | `agent.run.succeeded` / `agent.run.failed` |
| `agent_outputs` | `output.published.{output_type}` |
| `agent_recommendations` | `recommendation.raised.{action_type}` |
| `approval_log` | `recommendation.approved` / `.modified` / `.rejected` |
| `system_events` | the trigger stream as-is |
| `outcomes` | `outcome.recorded` |

Merged newest-first with a common shape (`event_id`, `source`, `created_at`,
`event_type`, `entity_type`, `entity_id`, `actor_id`, `payload`), so the Audit
UI is unchanged. `?entity_id=` narrows to one entity's story. Proven by
`test_audit_history_reconstructs_full_lifecycle_without_audit_collection`:
generated → reviewed → approved → PO created → reconciled → outcome, all six
sources present, and no `audit_events` collection anywhere.

## 14. `outcomes`

Written at PO closure. References `supplier_performance.performance_id` rather
than duplicating it. Fields: `outcome_id` (`OUT-{po_id}`), `recommendation_id`,
`purchase_order_id`, `supplier_id`, `product_id`, `performance_id`,
`promised_date`, `actual_date`, `ordered_qty`, `received_qty`, `fill_rate`,
`defect_rate`, `price_variance`, `delivery_variance_days`,
`reconciliation_status`, `exception_count`, `reconciliation_output_id`,
`recorded_at`, `schema_version`.

## 15. Ownership rules — enforced in code

`OutputRepository.publish()` raises `OwnershipViolation` if the envelope's
domain is not `procurement`, the agent is not R1–R5, or the `output_type` is a
foreign contract (`DemandForecast`, `InventoryPosition`, `ReorderNeed`,
`SafetyStockTarget`, …). Upstream fixtures are written through a separate,
explicitly named `seed_upstream_contract()` that accepts only the documented
upstream producers. Proven by four parametrized tests.

## 16. Indexes — `firebase/firestore.indexes.json`

| Collection | Fields | Backing query |
|---|---|---|
| `agent_state` | agent_id, entity_id, output_type | Latest-state lookups by producer/entity |
| `agent_outputs` | output_type, entity_id, generated_at DESC | `OutputRepository.history()` |
| `agent_recommendations` | status, risk_level, generated_at DESC | Review queue filtered by risk |
| `agent_recommendations` | status, generated_at DESC | Review queue (pre-existing) |
| `supplier_performance` | supplier_id, actual_date DESC | R2/R3 recent-history windows |
| `system_events` | event_type, created_at DESC | Event-type consumers |
| `supplier_quotes` | product_id, valid_until DESC | R1 quote selection (pre-existing) |

No `processed + created_at` index was added: no query in this codebase filters
on `processed` yet. Add it when a consumer does.

## 17. Firestore rules — `firebase/firestore.rules`

Every collection is matched explicitly; **there is no catch-all**. Firestore
ORs overlapping rule blocks, so a catch-all `allow write` would have silently
defeated the `allow write: if false` on protected collections. Anything not
listed is denied by default.

| Group | Read | Write |
|---|---|---|
| `agent_outputs`, `agent_state`, `agent_runs`, `system_events`, `approval_log`, `outcomes`, `agent_recommendations` | procurement role | **never** (backend only) |
| `products`, `inventory_snapshots`, `inventory_movements` | procurement role | **never** |
| Procurement operational collections | procurement role | procurement role |

Emulator-proven: a manager token is refused a direct write to every protected
collection (7 parametrized tests), can read them, cannot write shared context,
and an unlisted collection is closed to everyone.

## 18. Idempotency

| Scenario | Guarantee | Test |
|---|---|---|
| Same output published twice | One `agent_outputs` record | `test_republishing_same_output_is_idempotent` (+ Firestore variant) |
| Same output, different content | History untouched | `test_agent_outputs_is_append_only` |
| Older output after newer | State not regressed | `test_delayed_retry_cannot_regress_state` |
| Same event retried | One event | `test_deterministic_event_id_makes_retry_a_noop` |
| Same approval repeated | Second returns 409 | `test_rejected_recommendation_cannot_be_re_decided` |
| Same execution repeated | Same PO id, one event | `test_approval_journals_and_events_are_idempotent` |
| Same closure repeated | One outcome, one performance row | `test_repeated_close_does_not_duplicate_outcome` |
| Same reconciliation repeated | State reflects latest | `test_repeated_reconciliation_is_safe` |

## 19. Freshness

Unchanged Procurement contract: R4 refuses I2/I3/D4 evidence older than
**72 hours** and reports `stale_dependency`. `OutputRepository.get_latest_output`
enforces the hard floor (schema validity, `expires_at`) and *optionally* an age
limit; the coordinator deliberately leaves the age check to R4 so the guardrail
stays precise ("stale" rather than "missing"). Demo fixtures are stamped
"published now" at bootstrap because they are synthetic; CSV imports keep the
file's own `generated_at`.

## 20. Input traceability

Every published output carries `input_refs`. The coordinator resolves concrete
ids and passes them via `AgentContext.input_refs`; the agent's own evidence
labels are appended. For R4 that is the exact `output_id` of the D4, I2 and I3
state consumed plus the R1/R2/R3 output ids for every candidate. For R5 it is
the PO reference and the originating recommendation id. Proven end-to-end by
`test_full_input_to_output_trace_can_be_reconstructed` and the Firestore
`test_shared_architecture_end_to_end_trace`, which walks
`agent_outputs → input_refs → agent_outputs → agent_runs → agent_recommendations
→ approval_log → purchase_orders` from persisted records alone.

## 21. Team handoff matrix

**R1** — Reads `suppliers`, `supplier_quotes`. Publishes `SupplierComparison`.
Writes `agent_outputs`, `agent_state`.

**R2** — Reads `supplier_performance`, `goods_receipts`, R5 delivery facts (via
`supplier_performance`/`outcomes`). Publishes `SupplierReliabilityScore`. Writes
`agent_outputs`, `agent_state`.

**R3** — Reads `supplier_performance`, current delay facts, R5 delivery facts,
R2 `SupplierReliabilityScore`. Publishes `LeadTimeRisk`. Writes `agent_outputs`,
`agent_state`, and `system_events` when an operational signal is warranted
(`procurement.evidence.risk_elevated` on MEDIUM/HIGH).

**R4** — Reads `suppliers`, `supplier_quotes`, D4 `DemandForecast`, I1
`InventoryPosition` (available), I2 `ReorderNeed`, I3 `SafetyStockTarget`, R1
`SupplierComparison`, R2 `SupplierReliabilityScore`, R3 `LeadTimeRisk`.
Publishes `PurchaseRecommendation`. Writes `agent_outputs`, `agent_state`,
`agent_recommendations`, `system_events`.

**R5** — Reads `purchase_orders`, `goods_receipts`, `invoices`, approved R4
`PurchaseRecommendation`. Publishes `ProcurementException` and
delivery/reconciliation facts. Writes `agent_outputs`, `agent_state`,
`supplier_performance`, `outcomes`, `system_events`. **Only creates an
`agent_recommendation` when a separate explicit human action requires
approval** — the `ReconciliationReview` raised for a mismatch. A clean match
raises none.

R1–R3 never write `agent_recommendations`.

## 22. Team integration instructions

1. **Point Procurement at the shared project.** Set `AUTH_MODE=firebase`,
   `REPOSITORY_BACKEND=firestore`, `FIREBASE_PROJECT_ID`, and credentials via
   `FIREBASE_CREDENTIALS_JSON` or Application Default Credentials. All variables
   must be present before process start.
2. **Deploy the rules and indexes** in `firebase/` — the rules are the
   data-access control for the shared collections. Confirm no other domain
   ships a catch-all `allow write` rule, which would defeat these.
3. **Publish upstream contracts into `agent_state`.** Demand writes
   `state_id = "D4:DemandForecast:{product_id}"`; Inventory writes
   `I1:InventoryPosition:…`, `I2:ReorderNeed:…`, `I3:SafetyStockTarget:…`. Use
   the `SharedAgentOutput` envelope. R4 reads nothing else.
   **Set `ALLOW_UPSTREAM_FIXTURES=false` in the shared system.** Procurement is
   not the producer of these contracts. Its local fixture loader and the
   `/imports/{demand_forecasts|inventory_positions|reorder_needs|safety_stock_targets}`
   endpoints are **DEV/TEST COMPATIBILITY ONLY** — they exist so Procurement can
   run standalone. With the flag false, bootstrap skips them and the endpoints
   return 403; only Demand and Inventory write those contracts.
4. **Consume Procurement outputs from `agent_state`** by `state_id`
   (`R3:LeadTimeRisk:{supplier_id}`, `R4:PurchaseRecommendation:{product_id}`)
   or subscribe to `system_events` by `event_type`. Do not read
   `agent_recommendations` for intermediate evidence; it holds only actionable
   decisions.
5. **Approval goes through `POST /recommendations/{id}/decision`** — never a
   direct `approval_log` write. Execution through `POST /recommendations/{id}/execute`.
6. **Mint `role` custom claims** (`owner_manager`, `admin`,
   `procurement_manager`) on Firebase users; the rules and `require_manager`
   both key on them.
7. **Never enable `AUTH_MODE=demo`** outside a developer's own machine.

---

## 23. Alignment corrections against the specification (2026-09-14)

Direct review against `25_Agent_Firebase_Database_Architecture.pdf` found four
semantic differences in the first conformance pass. Each is corrected and
proven below.

| # | Difference found | Correction | Proof |
|---|---|---|---|
| 1 | R1–R3 were routed to `agent_recommendations` whenever risk was MEDIUM/HIGH | Routing is now by `output_type` only; `finalize_agent_result` forces `requires_approval=False` on every evidence contract. Elevated risk raises `procurement.evidence.risk_elevated` instead | 9 parametrized cases (R1/R2/R3 × LOW/MEDIUM/HIGH) → no recommendation, still in outputs/state; R4 consumes normally; Firestore e2e asserts no R1–R3 approval records |
| 2 | Every R5 result was routed to `agent_recommendations` as a closure gate | R5 output is evidence. Clean MATCH → no recommendation, closes directly. MISMATCH → `procurement.exception.created` **and** a separate `ReconciliationReview` action (`source_output_id` → R5 output) that must be approved before closure | `test_r5_clean_match_creates_no_recommendation_and_closes_directly`, `test_r5_mismatch_publishes_evidence_and_raises_separate_review_action`, `test_r5_mismatch_cannot_close_until_review_is_accepted`, Firestore `test_shared_r5_mismatch_raises_review_action_in_firestore`, 2 new Vitest cases, live UI |
| 3 | `audit_events` had been mapped onto `system_events`, and bookkeeping events (`data.imported`, `data.upserted`, `demo.bootstrap`, `job.*`) were being written there | `system_events` carries triggers only. Bookkeeping events removed. Audit history composed on read from six canonical sources (`services/audit_history.py`); `/audit` and the Audit UI unchanged in shape; `/events` exposes the raw trigger stream | `test_system_events_carry_no_bookkeeping_records`, `test_audit_history_reconstructs_full_lifecycle_without_audit_collection` (asserts no `audit_events` collection and all six sources present), Firestore e2e steps 29–30 |
| 4 | Upstream D4/I1/I2/I3 fixture publishing was not isolated from shared mode | Gated by `ALLOW_UPSTREAM_FIXTURES` (default true for development, **must be false in the shared system**). Bootstrap skips, import endpoints 403, `seed_upstream_contract()` raises. Marked DEV/TEST COMPATIBILITY ONLY in code and docs | `test_upstream_seeding_is_refused_in_shared_mode`, `test_upstream_import_endpoint_is_refused_in_shared_mode`, `test_bootstrap_skips_upstream_fixtures_in_shared_mode` |

Collection names: `goods_receipts` and `invoices` are the canonical receipt
and invoice collections; `supplier_invoices` and `audit_events` no longer
exist anywhere in code, fixtures or tests. No dual writes.

---

## 25. Cross-document compliance audit (2026-09-28)

All three authoritative documents were read directly and in full. 96 applicable
requirements extracted: **83 PASS · 7 PARTIAL · 0 FAIL · 6 NOT APPLICABLE**.
Full matrix with per-requirement citations:
[`REQUIREMENTS_TRACEABILITY_MATRIX.md`](REQUIREMENTS_TRACEABILITY_MATRIX.md).

### Defects found by reading the sources, and fixed

| Requirement | Defect | Fix |
|---|---|---|
| Blueprint p13 | The approval trigger was emitted as a generic `recommendation.decision`; the Blueprint names **`recommendation.approved`**, so a consumer could not subscribe by `event_type` | Emits `recommendation.approved` / `.modified` / `.rejected` per decision |
| Blueprint p13 | **`outcome.recorded`** was never emitted, so D5 and domain evaluators had no trigger | Emitted at PO closure with the procurement actuals |
| Firebase p8 | R3 did not emit **`supplier.performance.updated`**; only the closure path did | R3 emits it when its published risk band changes — the change-gate prevents the cycle the literal reading would create (see C-02) |
| Firebase p12 | Minimum index list includes `system_events` **processed status**; only `event_type + created_at` existed | Added `processed + created_at DESC` |
| Blueprint p16 | Acceptance criteria "PO logic respects MOQ / lead time" were tested at R1 only, never at R4 | Added `test_r4_raises_quantity_to_supplier_moq` and `test_r4_eta_comes_from_lead_time_risk_not_quoted_days` |

### Contradictions between the source documents

Recorded rather than silently resolved — full detail in the matrix §E.

- **C-01 receipts vs goods_receipts** — Firebase p3/p10/p11 say `receipts`; p8,
  the Procurement section, says `goods_receipts`. Used `goods_receipts` (more
  specific). One name, no alias.
- **C-02 who emits `supplier.performance.updated`** — Blueprint p13 lists R2/R3
  as *consumers*; Firebase p8 says R3 *emits* it. Both honoured; the change-gate
  prevents a cycle.
- **C-03 depth of end-to-end CI** — Blueprint p17 wants ≥1 e2e in CI; Firebase
  p13 wants the full shared-data trace. CI runs the in-memory e2e; the Firestore
  trace needs the emulator container and runs on demand.
- **C-04 `outcomes` ownership** — Firebase p3/p11 name a "shared evaluation
  pipeline" as canonical writer. Procurement writes only its own rows and now
  also emits `outcome.recorded`. **Team-lead reconciliation item.**

### Database-ready, against the Firebase document's own definition (p13)

| Criterion | Evidence |
|---|---|
| Run agents with shared test data | `test_shared_architecture_end_to_end_trace` — 30 steps on the Firestore emulator |
| Publish documented contracts through the common repository | `OutputRepository.publish()` is the sole path; agents cannot write the exchange collections |
| Read upstream contracts without internal imports | `get_latest_output` only; `OwnershipViolation` on any foreign publish |
| Survive retry/duplicate-event tests | 8 idempotency scenarios + `test_shared_retry_same_output_published_twice_in_firestore` |
| Show a complete input-to-output trace | e2e step 26 walks `agent_outputs → input_refs → agent_outputs → agent_runs → agent_recommendations → approval_log → purchase_orders` from persisted records alone |

---

## 24. Verification summary

| Check | Result |
|---|---|
| Backend, no emulators | **125 passed**, 68 skipped |
| Backend, with emulators | **193 passed**, 0 skipped |
| Shared-architecture unit suite | 62 tests (incl. 9 parametrized R1–R3 × LOW/MEDIUM/HIGH no-recommendation cases, R5 clean/mismatch split, audit composition, dev-only gates, Blueprint-named trigger events, R4 MOQ/lead-time acceptance) |
| Emulator suite (rules, adapter, auth, e2e trace, R5 mismatch review) | 68 tests |
| Frontend Vitest | 51 passed |
| Vite build | passed |
| Docker: config, build, up, smoke, down | passed — smoke read I2 from `agent_state`, R4 carried upstream `input_refs`, run trace and shared events present |
| Live browser on Firestore | Dashboard, supplier intelligence, R4, approval, PO, R5 MATCH, R5 MISMATCH, audit — all passed; exchange records verified directly in the emulator |
| Existing R1–R5 behavior | unchanged — 63 pre-existing tests green |
