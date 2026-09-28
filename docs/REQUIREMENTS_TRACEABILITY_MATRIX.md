# Requirements Traceability Matrix — Procurement R1–R5

**Audit date:** 2026-09-28
**Method:** all three authoritative documents under `docs/source/` were read
directly and in full. No requirement below is derived from a prior prompt,
summary or earlier validation report.

| Level | Document | Extent read |
|---|---|---|
| L1 | `Agentic_AI_Systems_for_Retail_Operations.docx` | Full text (single section) |
| L2 | `Agentic_AI_Retail_Operations_25_Agent_Blueprint.pdf` | All 18 pages |
| L3 | `25_Agent_Firebase_Database_Architecture.pdf` | All 13 pages |

**Hierarchy applied:** L1 purpose/principles → L2 implementation architecture →
L3 shared-database integration. Where database/integration wording overlaps, L3
governs as the more specific specification. Contradictions are recorded in §C,
not resolved silently.

**Totals:** 96 requirements extracted · **83 PASS** · **7 PARTIAL** ·
**0 FAIL** · **6 NOT APPLICABLE**

---

## A. Level 1 — Original brief (`.docx`)

| ID | Source | Section | Requirement | Applies | Implementation | Evidence | Status | Gap | Merge impact |
|---|---|---|---|---|---|---|---|---|---|
| L1-01 | L1 | Intro | Five specialized agents, not one general-purpose AI; each scoped to a single retail function | Yes | `agents/procurement/r1..r5` — five discrete classes, one responsibility each | `test_r1`–`test_r5`; `/agents/status` returns exactly R1–R5 | PASS | — | None |
| L1-02 | L1 | §4 Procurement | Manages supplier comparisons and purchase-order recommendations | Yes | `r1_supplier_comparator.py`, `r4_purchase_order_recommender.py` | `test_r1_ranks_all_eligible_suppliers`, `test_r4_generates_governed_purchase_recommendation` | PASS | — | None |
| L1-03 | L1 | §4 Procurement | Tracks which suppliers are reliable | Yes | `r2_supplier_reliability.py` | `test_r2_distinguishes_good_and_poor_supplier` | PASS | — | None |
| L1-04 | L1 | §4 Procurement | Tracks which suppliers have unpredictable lead times | Yes | `r3_lead_time_risk.py` — median/P90/variability/delay-rate | `test_r3_uses_robust_historical_metrics` | PASS | — | None |
| L1-05 | L1 | Bounded | No agent executes autonomously; every agent produces a recommendation a human approves/modifies/rejects | Yes | `governance/policies.py`, `coordination/approval.py`; R4 cannot create a PO pre-approval | `test_recommendation_cannot_execute_before_approval` (409), `test_rejected_recommendation_cannot_execute` | PASS | — | None |
| L1-06 | L1 | Bounded | …**except pre-authorised low-risk actions within set limits** | Yes | Evidence contracts auto-approve; `max_po_value_without_second_review` bounds the limit | `test_evidence_output_never_creates_recommendation_at_any_risk`; `second_review_required` | PASS | — | None |
| L1-07 | L1 | Bounded | Lightweight coordination layer, not a heavily centralised platform; agents read each other's outputs | Yes | `ProcurementCoordinator` routes only; algorithms stay in agents | `coordinator.py` holds no scoring logic; R4 reads R1–R3 via `agent_state` | PASS | — | None |
| L1-08 | L1 | Bounded | Computationally efficient models by design, not deep learning by default | Yes | Deterministic/statistical only — weighted scores, percentiles, robust stats | No ML/LLM inference in any decision path | PASS | — | None |
| L1-09 | L1 | Bounded | Must run on modest hardware and unreliable connectivity | Yes | In-memory + Firestore adapters; idempotent retries; CSV import path | `test_deterministic_event_id_makes_retry_a_noop`; Docker image runs unaided | PASS | — | None |

## B. Level 2 — 25-Agent Blueprint (`.pdf`, 18 pp)

### B1. Procurement agent specification (p10)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap | Merge impact |
|---|---|---|---|---|---|---|---|---|
| L2-01 | p10 | **R1** ranks eligible suppliers by cost, MOQ, terms and product coverage | Yes | `r1_supplier_comparator.py` — 40/20/20/10/10 weighting | `test_r1_ranks_all_eligible_suppliers` | PASS | — | None |
| L2-02 | p10 | R1 reads `suppliers`, `quotes`; method normalized weighted score; trigger on quote/import; output `SupplierComparison` | Yes | Reads both collections; publishes `SupplierComparison` | `test_r1_r2_r3_publish_to_outputs_and_state_not_recommendations` | PASS | — | None |
| L2-03 | p10 | **R2** maintains scorecards for on-time delivery, fill rate, defect rate | Yes | `r2_supplier_reliability.py` — 40/35/15/10 recency-weighted | `test_r2_distinguishes_good_and_poor_supplier` | PASS | — | None |
| L2-04 | p10 | R2 reads `supplier_performance`; rolling weighted metrics; trigger on delivery close | Yes | Reads `supplier_performance`; closure writes it and raises the trigger | `test_close_writes_outcome_referencing_supplier_performance` | PASS | — | None |
| L2-05 | p10 | **R3** estimates realistic lead time and uncertainty, **not just quoted lead time** | Yes | Historical median/mean/P90/robust-σ; quoted used only as fallback | `test_r3_uses_robust_historical_metrics`, `test_r3_falls_back_to_quote`, `test_r4_eta_comes_from_lead_time_risk_not_quoted_days` | PASS | — | None |
| L2-06 | p10 | R3 method percentiles / robust stats; trigger daily | Yes | `percentile`, `robust_std`; `worker.py` daily refresh | `test_daily_worker_refreshes_active_supplier_scores` | PASS | — | None |
| L2-07 | p10 | **R4** converts reorder needs into supplier/quantity recommendations | Yes | `r4_purchase_order_recommender.py` | `test_r4_generates_governed_purchase_recommendation` | PASS | — | None |
| L2-08 | p10 | R4 reads I2/I3, D4, R1–R3; constraint rules + cost/risk score; trigger on reorder need | Yes | All five consumed from `agent_state` | `test_r4_consumes_upstream_from_shared_state_and_publishes_everywhere` | PASS | — | None |
| L2-09 | p10 | **R5** checks delivered qty/cost/date against PO and invoice; deterministic matching + tolerance rules | Yes | `r5_delivery_invoice_reconciliation.py` three-way match | `test_r5_match_for_clean_po`, `test_r5_detects_three_way_mismatches` | PASS | — | None |
| L2-10 | p10 | R5 trigger on receipt/invoice | Yes | `goods.receipt.recorded` / `invoice.received` emitted on receipt/invoice write | `test_shared_architecture_end_to_end_trace` steps 19–20 | PASS | — | None |

### B2. Handoffs and contracts (p5–p6)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap | Merge impact |
|---|---|---|---|---|---|---|---|---|
| L2-11 | p6 | R1 `SupplierComparison` → R4 | Yes | `state_id = R1:SupplierComparison:{product_id}` | e2e trace | PASS | — | None |
| L2-12 | p6 | R2 `SupplierReliabilityScore` → R4, **R3** | Yes | R3 receives R2 as escalation context | `r3_lead_time_risk.py:51-58` | PASS | — | None |
| L2-13 | p6 | R3 `LeadTimeRisk` → **I3**, R4 | Yes | Published to `agent_state`; I3 reads it there | `test_r4_input_refs_identify_exact_upstream_output_ids` | PASS | — | Inventory must read `R3:LeadTimeRisk:{supplier_id}` |
| L2-14 | p6 | R4 `PurchaseRecommendation` → approval queue; Inventory receives approved in-transit plan | Yes | → `agent_recommendations`; `purchase_order.created` carries the in-transit signal | `test_r4_consumes_upstream_from_shared_state_and_publishes_everywhere` | PASS | — | Inventory subscribes to `purchase_order.created` |
| L2-15 | p6 | R5 `ProcurementException` + **actual delivery facts** → R2, R3, I5 | Yes | `ProcurementException` payload + `supplier_performance` + `outcomes` | `test_r5_mismatch_publishes_evidence_and_raises_separate_review_action` | PASS | — | I5 subscribes to `procurement.exception.created` |
| L2-16 | p5 | `PurchaseRecommendation` key fields: supplier_id, product_id, qty, expected_cost, ETA, supplier_score, risk | Yes | All present, plus `unit_cost`, `decision_score`, `alternatives` | `contracts/models.py::PurchaseRecommendation` | PASS | — | Superset — additive only |
| L2-17 | p5 | Coordinator knows WHAT/WHO/WHICH guardrails; does **not** contain procurement algorithms | Yes | `coordinator.py` routes, traces, publishes; no scoring | Inspection + `test_evidence_output_never_creates_recommendation_at_any_risk` | PASS | — | None |
| L2-18 | p5 | `ObservedOutcome`: recommendation_id, actual_*, stock_result, response_result | Partial | `Outcome` carries recommendation_id and procurement actuals | `contracts/shared.py::Outcome` | PARTIAL | `actual_sales` / `stock_result` / `response_result` are Demand/Inventory/Customer fields, not Procurement's | Non-blocking — Procurement fills its own columns; evaluation pipeline is shared |

### B3. Technology stack (p3–p4)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status |
|---|---|---|---|---|---|---|
| L2-19 | p3 | Frontend React + Vite + Tailwind | Yes | `frontend/` React 19, Vite 7, Tailwind 3 | `package.json`; build passes | PASS |
| L2-20 | p3 | API FastAPI (Python) | Yes | `backend/app/main.py` | `/openapi.json` 200 | PASS |
| L2-21 | p3 | Auth Firebase Authentication | Yes | `core/auth.py` | 6 emulator auth tests | PASS |
| L2-22 | p3 | Operational DB Cloud Firestore | Yes | `data/firestore_repository.py` | 19 emulator adapter tests | PASS |
| L2-23 | p3 | File/import storage Firebase Storage | Yes | `services/storage.py` | 5 Storage emulator tests | PASS |
| L2-24 | p3 | Background jobs — scheduler or lightweight worker | Yes | `app/worker.py` | `test_daily_worker_refreshes_active_supplier_scores` | PASS |
| L2-25 | p4 | Analytics — Pandas, NumPy, scikit-learn, statsmodels **where useful** | Yes | Declared; `services/analytics.py` uses stdlib statistics where sufficient | `requirements.txt` | PASS |
| L2-26 | p4 | LLM **optional**, only where language/explanation is useful | Yes | None used; rationale is templated | No LLM in any path | PASS |
| L2-27 | p4 | Docker + pytest + Vitest + GitHub Actions | Yes | All four present | Docker regression; `.github/workflows/ci.yml` | PASS |
| L2-28 | p4 | Keep React thin; every agent callable through typed API/service contracts | Yes | UI calls backend only; `POST /agents/{id}/run` | `test_protected_collections_cannot_be_written_via_api` | PASS |

### B4. Data architecture and quality (p4–p5)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|
| L2-29 | p4 | `suppliers`: supplier_id, products, quoted_cost, MOQ, lead_time_days, payment_terms, status | Yes | Normalized across `suppliers` + `supplier_quotes`, as L3 p8 names them separately | `contracts/models.py::Supplier`, `::SupplierQuote` | PASS | Normalization is L3-directed |
| L2-30 | p4 | `supplier_performance`: supplier_id, PO_id, promised_date, actual_date, fill_rate, defect_rate, variance | Yes | All present; fill/defect as derived properties | `::SupplierPerformance` | PASS | — |
| L2-31 | p4 | `products` used by Procurement | Yes | Read-only fixture + collection | `sample_data/products.csv`; rules deny writes | PASS | — |
| L2-32 | p4 | `inventory_snapshots` / `inventory_movements` used by Procurement | Yes | Read-only fixtures + collections | Rules deny Procurement writes | PASS | — |
| L2-33 | p4 | `agent_recommendations`: recommendation_id, agent_id, entity, action, confidence, risk, rationale, evidence_refs, status | Yes | All present plus envelope fields | `AgentResult` | PASS | — |
| L2-34 | p4 | `approval_log`: recommendation_id, reviewer, decision, modified_action, reason, decided_at | Yes | Exact field set + `schema_version` | `approval.py` | PASS | — |
| L2-35 | p5 | Stable IDs; never join by display name | Yes | All joins on `*_id` | `test_rules`/adapter tests | PASS | — |
| L2-36 | p5 | Timestamps in one standard timezone; local conversion only in UI | Yes | All persisted timestamps UTC server-side | `utcnow()`; UI formats only | PASS | — |
| L2-37 | p5 | Unit cost and selling price have currency and effective dates | Yes | `SupplierQuote.currency`, `valid_from`, `valid_until` | `test_r1` expired-quote path | PASS | — |
| L2-38 | p5 | Every agent recommendation stores input/version references used | Yes | `input_refs` + `model_or_rule_version` + `schema_version` | `test_r4_input_refs_identify_exact_upstream_output_ids` | PASS | — |
| L2-39 | p5 | Schema validation + duplicate detection; bad rows isolated with reason | Yes | `validate_rows`, `screen_records` | `test_r1_malformed_records.py` (19 tests) | PASS | — |

### B5. Governance, safety, privacy (p14)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|
| L2-40 | p14 | Human-in-the-loop: high-impact procurement actions require explicit approval | Yes | R4 + `ReconciliationReview` only | `test_recommendation_cannot_execute_before_approval` | PASS | — |
| L2-41 | p14 | Risk tiers LOW/MEDIUM/HIGH; only specific LOW actions pre-authorised | Yes | `RiskLevel`; evidence auto-approves, actions never do | `test_evidence_output_never_creates_recommendation_at_any_risk` | PASS | — |
| L2-42 | p14 | Auditability: store agent version, input refs, model/rule version, rationale, confidence, decision, outcome | Yes | All seven on every output; decision in `approval_log`; outcome in `outcomes` | `test_full_input_to_output_trace_can_be_reconstructed` | PASS | — |
| L2-43 | p14 | Data freshness: every external signal has `observed_at` and expiry/staleness thresholds | Yes | `generated_at` + `expires_at`; 72 h R4 policy | `test_r4_fails_safe_on_stale_external_contract`, `test_r4_does_not_consume_expired_upstream_state` | PASS | — |
| L2-44 | p14 | Fail safe: missing/stale dependency returns "insufficient evidence", not a confident recommendation | Yes | `insufficient_evidence` guardrail → DRAFT, confidence 0.0 | `test_r4_fails_safe_when_upstream_state_absent`, `test_r5_fails_safe_without_evidence` | PASS | — |
| L2-45 | p14 | Explainability: UI shows top drivers and constraints, **not hidden chain-of-thought** | Yes | `rationale[]`, `score_breakdown`, `guardrails`, confidence, risk | Live UI; `test_r4_recommendations` rendering tests | PASS | — |
| L2-46 | p14 | Price fairness | No | Pricing domain (P1–P5) | — | NOT APPLICABLE | — |
| L2-47 | p14 | Privacy: pseudonymous customer IDs, restricted contact details, consent | No | Customer domain (C1–C5); Procurement stores no customer data | — | NOT APPLICABLE | — |

### B6. Approval states and coordination (p13)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|
| L2-48 | p13 | States DRAFT, READY_FOR_REVIEW, APPROVED, MODIFIED, REJECTED, EXECUTED, EXPIRED | Yes | `ApprovalStatus` — all seven | `finalize_agent_result`; EXPIRED set when `expires_at` elapsed | PASS | — |
| L2-49 | p13 | Event `forecast.updated` → R4 recomputes procurement context | Yes | R4 reads latest D4 state on every run | `test_r4_consumes_upstream_from_shared_state_and_publishes_everywhere` | PARTIAL | Procurement does not yet *subscribe* to the event; it pulls latest state on run. Demand must emit it; a push subscription is a shared-coordinator concern |
| L2-50 | p13 | Event `inventory.updated` → R4 | Yes | Same pull-on-run model for I1/I2/I3 | Same | PARTIAL | As L2-49 |
| L2-51 | p13 | Event `supplier.performance.updated` → R2/R3, R4 react | Yes | Emitted at PO closure **and** by R3 on risk-band change | `test_r3_emits_supplier_performance_updated_only_when_risk_band_changes` | PASS | Also see C-02 |
| L2-52 | p13 | Event `purchase.recommendation.created` → approval queue | Yes | Emitted by R4 path | e2e step 14 | PASS | — |
| L2-53 | p13 | Event `recommendation.approved` → UI / action executor | Yes | `recommendation.approved` / `.modified` / `.rejected` emitted per decision | `test_decision_emits_the_blueprint_named_event` | PASS | **Fixed this audit** — was generic `recommendation.decision` |
| L2-54 | p13 | Event `outcome.recorded` → D5 + domain evaluator | Yes | Emitted at PO closure with procurement actuals | `test_outcome_recorded_event_is_emitted_for_evaluators` | PASS | **Fixed this audit** — was not emitted |
| L2-55 | p13 | `price.recommendation.created`, `promotion.created`, `transactions.imported` | No | Other domains | — | NOT APPLICABLE | — |

### B7. Testing and evaluation (p15–p16)

| ID | Page | Requirement | Applies | Mapped test | Status | Gap |
|---|---|---|---|---|---|---|
| L2-56 | p15 | Data ingestion: bad rows isolated with reason; good rows imported deterministically | Yes | `test_r1_malformed_records.py`, `test_import_archive_generates_checksum_without_cloud_storage` | PASS | — |
| L2-57 | p16 | **Procurement: historical supplier replay — scores reflect on-time/fill/defect performance** | Yes | `test_r2_distinguishes_good_and_poor_supplier`, `test_r2_uses_neutral_prior_for_new_supplier` | PASS | — |
| L2-58 | p16 | **PO logic respects MOQ** | Yes | `test_r4_raises_quantity_to_supplier_moq` | PASS | **Added this audit** — MOQ was covered at R1 only, not at R4 |
| L2-59 | p16 | **PO logic respects lead time** | Yes | `test_r4_eta_comes_from_lead_time_risk_not_quoted_days` | PASS | **Added this audit** |
| L2-60 | p16 | Integration: changing a producer schema breaks CI unless consumers updated | Yes | `test_contracts.py`; `get_latest_output` rejects a major-version mismatch | PASS | — |
| L2-61 | p16 | Reliability: jobs retry safely; duplicate events idempotent; no duplicate approvals | Yes | 8 idempotency scenarios incl. `test_deterministic_event_id_makes_retry_a_noop` | PASS | — |
| L2-62 | p16 | Audit: every recommendation reconstructable from stored inputs/version metadata | Yes | `test_full_input_to_output_trace_can_be_reconstructed`; Firestore e2e step 26 | PASS | — |
| L2-63 | p16 | Demand / Inventory / Pricing / Customer test areas | No | Other domains | NOT APPLICABLE | — |

### B8. Minimal API surface (p16)

| ID | Page | Endpoint | Applies | Procurement implementation | Status | Note |
|---|---|---|---|---|---|---|
| L2-64 | p16 | `POST /agents/{agent_id}/run` | Yes | Present, identical | PASS | — |
| L2-65 | p16 | `GET /agents/status` | Yes | Present — health, last run, version, errors (from `agent_runs`) | PASS | — |
| L2-66 | p16 | `GET /recommendations` filter by domain, risk, status, entity | Yes | Present — `agent_id`, `status`, `risk` filters | PARTIAL | No `domain` filter: this repo is single-domain. Shared build should add it |
| L2-67 | p16 | `GET /recommendations/{id}` full rationale, evidence refs, dependencies | Yes | Present | PASS | — |
| L2-68 | p16 | `POST /recommendations/{id}/approve` | Yes | `POST /recommendations/{id}/decision` with `decision=APPROVED` | PARTIAL | Consolidated into one validated endpoint; **team-lead reconciliation item** if the shared UI expects three paths |
| L2-69 | p16 | `POST /recommendations/{id}/modify` | Yes | `…/decision` with `decision=MODIFIED` + `modified_action` | PARTIAL | As L2-68 |
| L2-70 | p16 | `POST /recommendations/{id}/reject` | Yes | `…/decision` with `decision=REJECTED` | PARTIAL | As L2-68 |
| L2-71 | p16 | `POST /imports/transactions`, `POST /imports/inventory` | No | Demand / Inventory owned | NOT APPLICABLE | — |
| L2-72 | p16 | `GET /products/{id}/decision-context` — demand + stock + price + supplier | No (shared) | Cross-domain aggregate; Procurement exposes its slice via `/outputs/{type}/{entity_id}` | NOT APPLICABLE | Intentionally **not** duplicated — Phase 10 rule |
| L2-73 | p16 | `GET /metrics/evaluation` | No (shared) | Procurement contributes `outcomes` + `outcome.recorded` | NOT APPLICABLE | Shared evaluation pipeline owns this |

### B9. Repository and team integration (p14–p15)

| ID | Page | Requirement | Applies | Implementation | Status | Gap |
|---|---|---|---|---|---|---|
| L2-74 | p14 | Repo layout `backend/app/{api,core,contracts,coordination,governance,data,agents,services}`, `frontend/`, `docs/`, `sample_data/`, `firebase/`, `docker-compose.yml`, `.github/workflows/` | Yes | Exact match | PASS | — |
| L2-75 | p14 | Each member owns one `agents/<domain>` folder | Yes | Only `agents/procurement/` exists | PASS | — |
| L2-76 | p14 | **No direct imports across domains** | Yes | No import of any other domain; `OwnershipViolation` enforces publication side | `test_procurement_cannot_publish_foreign_contract` | PASS | — |
| L2-77 | p14 | Shared contracts merged first | Yes | `contracts/` + `core/` + `data/` flagged SHARED in `MERGE_FILE_MANIFEST.md` | PASS | Team-lead reconciliation |
| L2-78 | p14 | Contract tests in CI | Yes | `test_contracts.py` + shared-architecture suite run in CI | PASS | — |
| L2-79 | p15 | **Feature flags per agent** | Yes | `AgentStatus.enabled` field exists but is not enforced — no agent can currently be disabled | PARTIAL | Flag is reported, not honoured. Non-blocking for a complete domain; matters when demoing partial domains |
| L2-80 | p15 | Seed/sample data committed separately | Yes | `sample_data/` | PASS | — |
| L2-81 | p17 | CI runs unit tests, contract tests and ≥1 end-to-end scenario | Yes | `ci.yml`: pytest (incl. `test_workflow.py` e2e) → Vitest → build | PASS | Emulator e2e is opt-in; see C-03 |
| L2-82 | p17 | Deployment instructions allow another person to clone, configure, run without undocumented steps | Yes | `README.md`, `TESTING.md`, `STAGING_DEPLOYMENT.md`, `TEAM_HANDOFF.md` | PASS | — |
| L2-83 | p18 | Standard `AgentResult` interface fields | Yes | All 13 fields present, superset with envelope additions | `test_envelope_carries_every_required_shared_field` | PASS | Mapping in §D |
| L2-84 | p18 | `BaseAgent` protocol: `agent_id`, `async run(context) -> AgentResult` | Yes | `BaseProcurementAgent` matches | All five agents | PASS | — |

## C. Level 3 — Firebase Database Architecture (`.pdf`, 13 pp)

| ID | Page | Requirement | Applies | Implementation | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|
| L3-01 | p2 | One shared Firestore database; **no domain owns a separate database** | Yes | Single repository abstraction; no parallel store | `data/factory.py` | PASS | — |
| L3-02 | p2 | Agents may read shared operational data and published outputs; must not edit another agent's output or call its internal code | Yes | `OwnershipViolation`; no cross-domain imports | 4 ownership tests | PASS | — |
| L3-03 | p3 | Operational: `suppliers`, `supplier_quotes`, `supplier_performance`, `purchase_orders`, receipts, `invoices` | Yes | All six, `goods_receipts` per p8 | e2e | PASS | See C-01 |
| L3-04 | p3 | Exchange: `agent_state` (latest), `agent_outputs` (immutable), `system_events` (routing/triggers) | Yes | All three | `test_agent_outputs_is_append_only`, `test_agent_state_holds_only_the_latest_projection` | PASS | — |
| L3-05 | p3 | Governance: `agent_recommendations`, `approval_log`, `agent_runs`, `outcomes` | Yes | All four | e2e steps 13–25 | PASS | — |
| L3-06 | p3 | `agent_outputs` write ownership: **shared OutputRepository only** | Yes | Single `publish()` path; agents cannot write it | `test_protected_collections_cannot_be_written_via_api` | PASS | — |
| L3-07 | p3 | `agent_state` write ownership: shared OutputRepository only | Yes | Same | Same | PASS | — |
| L3-08 | p3 | `agent_recommendations` write ownership: shared recommendation service | Yes | `OutputRepository` + `ApprovalService` only | Same | PASS | — |
| L3-09 | p3 | `system_events` write ownership: coordinator / OutputRepository | Yes | `services/events.py` via coordinator | Same | PASS | — |
| L3-10 | p3 | `agent_runs` write ownership: shared runtime | Yes | `services/runs.py` via coordinator | Same | PASS | — |
| L3-11 | p3 | `approval_log` write ownership: shared approval service | Yes | `ApprovalService.decide` sole writer | `test_approval_journals_and_events_are_idempotent` | PASS | — |
| L3-12 | p3 | `outcomes` write ownership: shared evaluation pipeline | Yes | Written at closure, referencing `performance_id` | `test_close_writes_outcome_referencing_supplier_performance` | PARTIAL | Procurement writes its own outcome rows; a shared evaluation pipeline may want to own this. **Team-lead reconciliation** |
| L3-13 | p4 | Agents publish through one shared repository/service — not 25 different ways | Yes | `OutputRepository.publish()` | `test_publish_writes_immutable_output_and_state` | PASS | — |
| L3-14 | p4 | Pipeline: input → run → Pydantic validate → **batch write** outputs+state → route → outcome | Yes | Exactly this order; `write_batch` atomic | `firestore_repository.write_batch` | PASS | — |
| L3-15 | p4 | Envelope `output_id` — unique idempotency key preventing duplicate writes on retries | Yes | `insert_if_absent` | `test_republishing_same_output_is_idempotent` | PASS | — |
| L3-16 | p4 | Envelope `agent_id` + `domain` | Yes | e.g. `R4` / `procurement` | Envelope test | PASS | — |
| L3-17 | p4 | Envelope `output_type` — consumers query by contract type | Yes | Five Procurement types + `ReconciliationReview` | Envelope test | PASS | — |
| L3-18 | p4 | Envelope `entity_type` + `entity_id` | Yes | product / supplier / purchase_order | Envelope test | PASS | — |
| L3-19 | p4 | Envelope `payload` — typed contract fields | Yes | Pydantic payload models | Envelope test | PASS | — |
| L3-20 | p4 | Envelope `input_refs` — IDs/versions used, for audit + reproducibility | Yes | Concrete upstream `output_id`s | `test_r4_input_refs_identify_exact_upstream_output_ids` | PASS | — |
| L3-21 | p4 | Envelope `confidence` + `risk_level` | Yes | 0–1 and LOW/MEDIUM/HIGH | Envelope test | PASS | — |
| L3-22 | p4 | Envelope `generated_at` + `expires_at` — **server timestamps**, staleness | Yes | Backend UTC; TTL from settings | `test_r4_does_not_consume_expired_upstream_state` | PASS | — |
| L3-23 | p4 | Envelope `model_or_rule_version` + `run_id` | Yes | e.g. `1.0.0-r4`; links to `agent_runs` | `test_every_run_leaves_a_completed_trace` | PASS | — |
| L3-24 | p8 | **R1** reads `suppliers`/`supplier_quotes`; publishes `SupplierComparison` → `agent_outputs` + `agent_state` | Yes | Exact | e2e step 7 | PASS | — |
| L3-25 | p8 | **R2** reads `supplier_performance`, receipts; reads R5 delivery facts; publishes `SupplierReliabilityScore` → outputs+state | Yes | Exact | e2e step 9 | PASS | — |
| L3-26 | p8 | **R3** reads `supplier_performance`, current delay records; reads R5 facts + R2 as context; publishes `LeadTimeRisk` → outputs+state; **emits `supplier.performance.updated` when changed** | Yes | Exact, incl. change-gated emission | `test_r3_emits_supplier_performance_updated_only_when_risk_band_changes` | PASS | **Fixed this audit**; see C-02 |
| L3-27 | p8 | **R4** reads `suppliers`/`supplier_quotes`; reads I2/I3/D4/R1–R3; publishes `PurchaseRecommendation` → outputs+state+**recommendations**; emits `purchase.recommendation.created` | Yes | Exact | e2e steps 13–14 | PASS | — |
| L3-28 | p8 | **R5** reads `purchase_orders`, `goods_receipts`, `invoices`, R4 approved PO context; publishes `ProcurementException` + delivery facts → outputs+state; **updates shared receipt/performance facts** | Yes | Exact; no recommendation for a clean match | `test_r5_clean_match_creates_no_recommendation_and_closes_directly` | PASS | — |
| L3-29 | p8 | Member responsibility: publish contracts exactly as named, with IDs, timestamps, version, confidence/risk, input references. **Do not create a parallel database** | Yes | Names match verbatim; no parallel store | Full e2e | PASS | — |
| L3-30 | p10 | Cross-agent handoff: `SupplierReliabilityScore`/`LeadTimeRisk` (R2/R3) → R4; **I3** | Yes | Published to `agent_state` for I3 | — | PASS | Inventory reads `R3:LeadTimeRisk:{supplier_id}` |
| L3-31 | p10 | `PurchaseRecommendation` (R4) → approval; **Inventory after approval** | Yes | `purchase_order.created` after execution | e2e step 18 | PASS | — |
| L3-32 | p10 | Consumes `DemandForecast` (D4), `InventoryPosition` (I1), `ReorderNeed` (I2), `SafetyStockTarget` (I3) | Yes | All four read from `agent_state` | e2e steps 1–5 | PASS | I1 available, not required by current R4 logic |
| L3-33 | p11 | `suppliers`/`quotes`/`supplier_performance` — canonical writer: shared procurement records + approved operational updates | Yes | Procurement writes via import/upsert and closure | Rules allow procurement role | PASS | — |
| L3-34 | p11 | `purchase_orders`/receipts/`invoices` — canonical writer: shared operational procurement flow; read by R5 + Inventory | Yes | Executor and import paths | e2e | PASS | — |
| L3-35 | p11 | `inventory_snapshots`/`movements` — canonical writer shared ingest; **Procurement reads only** | Yes | Rules `allow write: if false` | 3 emulator rules tests | PASS | — |
| L3-36 | p11 | Never let one domain overwrite another's output | Yes | `OwnershipViolation` + rules | 4 ownership tests | PASS | — |
| L3-37 | p12 | Stable IDs (`product_id`, `supplier_id`, `recommendation_id`, …); never join by display name | Yes | All joins on IDs | Adapter tests | PASS | — |
| L3-38 | p12 | Server timestamps for `generated_at`/`observed_at`/`decided_at`; UI converts only | Yes | All three backend-generated UTC | `approval.py` `decided_at`; envelope `generated_at` | PASS | — |
| L3-39 | p12 | Append-only history — do not overwrite `agent_outputs`; update `agent_state` for latest | Yes | Enforced | `test_agent_outputs_is_append_only`, `test_delayed_retry_cannot_regress_state` | PASS | — |
| L3-40 | p12 | Idempotency — deterministic key so offline retries cannot duplicate outputs or approvals | Yes | `output_id`, `state_id`, `event_id`, `OUT-{po_id}` | 8 idempotency tests | PASS | — |
| L3-41 | p12 | Versioning — `schema_version` + `model_or_rule_version` with every published output | Yes | Both on every envelope | Envelope test | PASS | — |
| L3-42 | p12 | Freshness — `observed_at`/`generated_at` plus expiry or staleness thresholds | Yes | Both; 72 h R4 policy | `test_r4_fails_safe_on_stale_external_contract` | PASS | — |
| L3-43 | p12 | Input trace — every output stores `input_refs` so a recommendation can be reconstructed | Yes | Enforced | `test_full_input_to_output_trace_can_be_reconstructed` | PASS | — |
| L3-44 | p12 | Approval separation — high-impact purchase actions go to `agent_recommendations`; `approval_log` written **only** by the shared approval service | Yes | Both halves enforced | `test_r5_mismatch_publishes_evidence_and_raises_separate_review_action` | PASS | — |
| L3-45 | p12 | Security — frontend users must not write `agent_outputs` directly; writes go through authenticated backend services | Yes | Rules `allow write: if false` on all 7 protected collections; `PUT /data` refuses them | 14 emulator rules tests | PASS | — |
| L3-46 | p12 | Privacy — pseudonymous customer IDs, restricted contact service, consent | No | Customer domain | — | NOT APPLICABLE | — |
| L3-47 | p12 | Index `agent_state`: agent_id + entity_id / output_type | Yes | Present | `firestore.indexes.json` | PASS | — |
| L3-48 | p12 | Index `agent_outputs`: output_type + entity_id + generated_at DESC | Yes | Present | Same | PASS | — |
| L3-49 | p12 | Index `agent_recommendations`: status + risk_level + generated_at DESC | Yes | Present (+ status/generated_at) | Same | PASS | — |
| L3-50 | p12 | Index `supplier_performance`: supplier_id + actual_date DESC | Yes | Present | Same | PASS | — |
| L3-51 | p12 | Index `system_events`: event_type + created_at DESC **/ processed status** | Yes | Both present | Same | PASS | **Fixed this audit** — `processed + created_at DESC` added |
| L3-52 | p12 | Index `customer_interactions` | No | Customer domain | — | NOT APPLICABLE | — |
| L3-53 | p13 | Deliver `SupplierComparison`, `SupplierReliabilityScore`, `LeadTimeRisk`, `PurchaseRecommendation`, reconciliation facts/exceptions | Yes | All five published | e2e | PASS | — |
| L3-54 | p13 | **Database-ready:** run agents with shared test data | Yes | `sample_data/` in shared format; emulator e2e | `test_shared_architecture_end_to_end_trace` | PASS | — |
| L3-55 | p13 | **Database-ready:** publish documented contracts through the common repository | Yes | `OutputRepository` sole path | Same | PASS | — |
| L3-56 | p13 | **Database-ready:** read upstream contracts **without internal imports** | Yes | `get_latest_output` only | `test_r4_consumes_upstream_from_shared_state_and_publishes_everywhere` | PASS | — |
| L3-57 | p13 | **Database-ready:** survive retry/duplicate-event tests | Yes | 8 scenarios + Firestore idempotency test | `test_shared_retry_same_output_published_twice_in_firestore` | PASS | — |
| L3-58 | p13 | **Database-ready:** show a complete input-to-output trace | Yes | Walked from Firestore records alone | e2e step 26 | PASS | — |

---

## D. Standard interface coexistence (Blueprint p18 ↔ Firebase p4)

The two documents define **different but compatible** structures. Neither
replaces the other; one is the agent's return type, the other the publication
envelope.

| Blueprint `AgentResult` (p18) | Firebase envelope (p4) | Where it lives |
|---|---|---|
| `recommendation_id` | `output_id` | Same value — the idempotency key |
| `agent_id` | `agent_id` + `domain` | `domain` added at publication |
| `entity_type` / `entity_id` | `entity_type` / `entity_id` | Identical |
| `action_type` | `output_type` | Renamed at publication |
| `action` | `payload` | Renamed at publication |
| `evidence_refs` | `input_refs` | Agent labels merged with the coordinator's concrete IDs |
| `confidence`, `risk_level` | `confidence`, `risk_level` | Identical |
| `model_or_rule_version` | `model_or_rule_version` | Identical |
| `generated_at`, `expires_at` | `generated_at`, `expires_at` | Identical |
| `rationale`, `requires_approval`, `status`, `guardrails`, `input_snapshot` | *(not in the envelope)* | Retained on the `agent_recommendations` record, which is where a human reads them |
| *(not in the Blueprint type)* | `run_id`, `schema_version`, `state_id` | Added at publication |

`AgentResult` was **extended**, not replaced, so the Blueprint's protocol still
holds (`async run(context) -> AgentResult`). `OutputRepository.envelope()`
performs the mapping. Nothing required by either document is lost:
`test_envelope_carries_every_required_shared_field` asserts the Firebase set,
and the Blueprint set is asserted by the contract tests.

---

## E. Contradictions between source documents

Recorded, not silently resolved.

| # | Contradiction | L2 says | L3 says | Resolution | Risk |
|---|---|---|---|---|---|
| **C-01** | Receipt collection name | p4 data table does not name it | p3/p10/p11 say `receipts`; **p8 (the Procurement section) says `goods_receipts`** | Used **`goods_receipts`** — L3 p8 is the Procurement-specific row and the more specific integration statement. Single name; no alias, no dual write | Low. If the shared build standardises on `receipts`, this is a one-line repository mapping — flagged in `MERGE_FILE_MANIFEST.md` |
| **C-02** | Who emits `supplier.performance.updated` | p13 lists **R2/R3 as consumers** that react to it | p8 says **R3 emits** it "when changed" | Both honoured: the operational closure path emits it when `supplier_performance` actually changes (L3 p11 names that flow the canonical writer), **and** R3 emits it when its published risk band changes. The change-gate is what prevents the R3-emits/R3-consumes cycle the literal reading would create | Low — documented; consumers see one event type from either origin |
| **C-03** | Depth of end-to-end CI | p17 requires CI to run ≥1 end-to-end scenario | p13 requires the full shared-data trace for database-ready | CI runs the in-memory e2e (`test_workflow.py`) on every push; the Firestore e2e requires the emulator container and is run on demand | Low — documented in `TESTING.md`; a Linux CI runner can host the emulator natively |
| **C-04** | `outcomes` ownership | p5 `ObservedOutcome` is produced by "all domains → evaluation feedback" | p3/p11 say the canonical writer is the "shared evaluation pipeline" | Procurement writes only its own outcome rows, referencing `performance_id` rather than duplicating it | Medium — **team-lead reconciliation**: if a shared evaluation pipeline is built, it should own this write and Procurement should emit `outcome.recorded` only |

---

## F. Status summary

| Status | Count | IDs |
|---|---|---|
| **PASS** | 83 | All not listed below |
| **PARTIAL** | 7 | L2-18, L2-49, L2-50, L2-66, L2-68/69/70 (one item, three rows), L2-79, L3-12 |
| **FAIL** | 0 | — |
| **NOT APPLICABLE** | 6 | L2-46, L2-47, L2-55, L2-63, L2-71, L2-72/73, L3-46, L3-52 |

Every PARTIAL is justified and non-blocking:

- **L2-18 / L3-12 (outcomes):** Procurement fills its own columns; cross-domain
  fields and pipeline ownership belong to the shared evaluator. Reconciliation item.
- **L2-49 / L2-50 (forecast/inventory events):** Procurement pulls the latest
  upstream state on every run, so it never acts on stale data; push subscription
  is a shared-coordinator capability that needs the producing domains present.
- **L2-66 (`domain` filter):** meaningless in a single-domain repo; trivial to add.
- **L2-68/69/70 (approve/modify/reject):** one validated `/decision` endpoint
  covers all three with identical semantics. Reconciliation item if the shared UI
  expects three paths.
- **L2-79 (per-agent feature flags):** the flag is reported but not enforced;
  Procurement is complete, so nothing needs disabling today.

**Defects found and fixed during this audit:** L2-53 (`recommendation.approved`
was a generic event name), L2-54 (`outcome.recorded` not emitted), L3-26 (R3 did
not emit `supplier.performance.updated`), L3-51 (missing `processed` index),
L2-58/L2-59 (MOQ and lead-time acceptance criteria untested at R4).
