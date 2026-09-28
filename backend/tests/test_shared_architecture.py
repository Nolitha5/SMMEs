"""Shared 25-agent exchange-layer conformance.

Runs against the in-memory repository. The same behaviours are proven against
the Firestore emulator in test_firebase_emulator.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.contracts.models import AgentContext, AgentResult, ApprovalDecision, RiskLevel
from app.contracts.shared import (
    COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_AGENT_RUNS,
    COLLECTION_AGENT_STATE, COLLECTION_APPROVAL_LOG, COLLECTION_OUTCOMES, COLLECTION_SYSTEM_EVENTS,
    PROTECTED_COLLECTIONS, SCHEMA_VERSION, SharedAgentOutput, state_id,
)
from app.coordination.approval import ApprovalService
from app.coordination.coordinator import ProcurementCoordinator
from app.data.output_repository import OutputRepository, OwnershipViolation
from app.main import app
from app.services import events


def _result(**overrides) -> AgentResult:
    base = dict(
        recommendation_id="REC-test-0001", output_id="REC-test-0001", run_id="RUN-test-0001",
        agent_id="R1", entity_type="product", entity_id="SKU-100",
        action_type="SupplierComparison", action={"product_id": "SKU-100", "ranked_suppliers": []},
        rationale=["test"], evidence_refs=["suppliers", "supplier_quotes"], input_refs=["suppliers"],
        confidence=0.8, risk_level=RiskLevel.LOW, requires_approval=False,
        model_or_rule_version="1.0.0-r1",
    )
    base.update(overrides)
    return AgentResult(**base)


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


def test_envelope_carries_every_required_shared_field(repo):
    env = OutputRepository.envelope(_result())
    required = {
        "output_id", "agent_id", "domain", "output_type", "entity_type", "entity_id", "payload",
        "input_refs", "confidence", "risk_level", "generated_at", "expires_at",
        "model_or_rule_version", "run_id", "schema_version",
    }
    dumped = env.model_dump()
    assert required <= set(dumped)
    assert env.domain == "procurement"
    assert env.output_type == "SupplierComparison"
    assert env.schema_version == SCHEMA_VERSION
    assert env.state_id == state_id("R1", "SupplierComparison", "SKU-100")


def test_envelope_requires_run_id(repo):
    with pytest.raises(ValueError):
        OutputRepository.envelope(_result(run_id=None))


# ---------------------------------------------------------------------------
# agent_outputs append-only / agent_state latest / idempotency
# ---------------------------------------------------------------------------


def test_publish_writes_immutable_output_and_state(repo):
    outputs = OutputRepository(repo)
    env = outputs.publish(_result())

    stored = repo.get(COLLECTION_AGENT_OUTPUTS, env.output_id, "output_id")
    assert stored and stored["payload"] == {"product_id": "SKU-100", "ranked_suppliers": []}

    state = repo.get(COLLECTION_AGENT_STATE, env.state_id, "state_id")
    assert state and state["output_id"] == env.output_id


def test_republishing_same_output_is_idempotent(repo):
    outputs = OutputRepository(repo)
    r = _result()
    outputs.publish(r)
    outputs.publish(r)
    outputs.publish(r)
    rows = [o for o in repo.list(COLLECTION_AGENT_OUTPUTS) if o["output_id"] == "REC-test-0001"]
    assert len(rows) == 1


def test_agent_outputs_is_append_only(repo):
    outputs = OutputRepository(repo)
    outputs.publish(_result(confidence=0.5))
    # A second publish with the same id but different content must NOT overwrite history.
    outputs.publish(_result(confidence=0.9))
    stored = repo.get(COLLECTION_AGENT_OUTPUTS, "REC-test-0001", "output_id")
    assert stored["confidence"] == 0.5


def test_agent_state_holds_only_the_latest_projection(repo):
    outputs = OutputRepository(repo)
    t0 = datetime.now(timezone.utc)
    outputs.publish(_result(output_id="REC-a", recommendation_id="REC-a", generated_at=t0, confidence=0.5))
    outputs.publish(_result(output_id="REC-b", recommendation_id="REC-b", generated_at=t0 + timedelta(seconds=5), confidence=0.9))

    state = repo.get(COLLECTION_AGENT_STATE, state_id("R1", "SupplierComparison", "SKU-100"), "state_id")
    assert state["output_id"] == "REC-b"
    assert len([o for o in repo.list(COLLECTION_AGENT_OUTPUTS) if o["entity_id"] == "SKU-100"]) >= 2


def test_delayed_retry_cannot_regress_state(repo):
    """An older output arriving after a newer one must not overwrite state."""
    outputs = OutputRepository(repo)
    t0 = datetime.now(timezone.utc)
    outputs.publish(_result(output_id="REC-new", recommendation_id="REC-new", generated_at=t0 + timedelta(minutes=1)))
    outputs.publish(_result(output_id="REC-old", recommendation_id="REC-old", generated_at=t0))
    state = repo.get(COLLECTION_AGENT_STATE, state_id("R1", "SupplierComparison", "SKU-100"), "state_id")
    assert state["output_id"] == "REC-new"


# ---------------------------------------------------------------------------
# Ownership boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("foreign", ["DemandForecast", "ReorderNeed", "SafetyStockTarget", "InventoryPosition"])
def test_procurement_cannot_publish_foreign_contract(repo, foreign):
    with pytest.raises(OwnershipViolation):
        OutputRepository(repo).publish(_result(action_type=foreign))


def test_procurement_cannot_publish_for_another_domain(repo):
    with pytest.raises(OwnershipViolation):
        OutputRepository(repo).publish(_result(domain="inventory"))


def test_upstream_seed_rejects_unknown_producer(repo):
    with pytest.raises(OwnershipViolation):
        OutputRepository(repo).seed_upstream_contract("R4", "SKU-100", {})


def test_upstream_seed_is_the_only_way_to_write_foreign_state(repo):
    env = OutputRepository(repo).seed_upstream_contract("I2", "SKU-999", {
        "product_id": "SKU-999", "reorder_point": 10, "projected_position": 2,
        "reorder_needed": True, "recommended_qty": 50,
    })
    assert env.domain == "inventory"
    assert env.agent_id == "I2"
    assert repo.get(COLLECTION_AGENT_STATE, env.state_id, "state_id")


# ---------------------------------------------------------------------------
# R1–R5 publish through the shared path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_r2_r3_publish_to_outputs_and_state_not_recommendations(repo):
    coord = ProcurementCoordinator(repo)
    r1 = await coord.run_agent("R1", AgentContext(entity_type="product", entity_id="SKU-100", payload={"requested_qty": 260}))
    r2 = await coord.run_agent("R2", AgentContext(entity_type="supplier", entity_id="SUP-001", payload={"supplier_id": "SUP-001"}))
    r3 = await coord.run_agent("R3", AgentContext(entity_type="supplier", entity_id="SUP-001", payload={"supplier_id": "SUP-001"}, prior_outputs={"R2": r2.action}))

    for res, out_type in ((r1, "SupplierComparison"), (r2, "SupplierReliabilityScore"), (r3, "LeadTimeRisk")):
        assert repo.get(COLLECTION_AGENT_OUTPUTS, res.output_id, "output_id"), f"{out_type} missing from agent_outputs"
        assert repo.get(COLLECTION_AGENT_STATE, state_id(res.agent_id, out_type, res.entity_id), "state_id")
        # Evidence contracts never become review items, whatever their risk.
        assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, res.output_id, "recommendation_id") is None, \
            f"{out_type} must never be routed to agent_recommendations"
        assert res.requires_approval is False


# ---------------------------------------------------------------------------
# Evidence vs action: R1–R3 never raise approvals at any risk tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent_id,output_type,entity", [
    ("R1", "SupplierComparison", "SKU-100"),
    ("R2", "SupplierReliabilityScore", "SUP-001"),
    ("R3", "LeadTimeRisk", "SUP-001"),
])
@pytest.mark.parametrize("risk", [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])
def test_evidence_output_never_creates_recommendation_at_any_risk(repo, agent_id, output_type, entity, risk):
    from app.governance.policies import finalize_agent_result

    res = finalize_agent_result(_result(
        output_id=f"REC-{agent_id}-{risk.value}", recommendation_id=f"REC-{agent_id}-{risk.value}",
        agent_id=agent_id, action_type=output_type, entity_type="supplier" if agent_id != "R1" else "product",
        entity_id=entity, risk_level=risk, requires_approval=True,  # even if an agent asked for it
        model_or_rule_version=f"1.0.0-{agent_id.lower()}",
    ))
    OutputRepository(repo).publish(res)

    assert res.requires_approval is False
    assert res.status.value == "APPROVED"
    assert repo.get(COLLECTION_AGENT_OUTPUTS, res.output_id, "output_id")
    assert repo.get(COLLECTION_AGENT_STATE, state_id(agent_id, output_type, entity), "state_id")
    assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, res.output_id, "recommendation_id") is None


@pytest.mark.asyncio
async def test_elevated_risk_evidence_raises_event_not_review(repo, monkeypatch):
    """A MEDIUM/HIGH evidence output signals via system_events, not approval."""
    coord = ProcurementCoordinator(repo)
    r3 = await coord.run_agent("R3", AgentContext(entity_type="supplier", entity_id="SUP-001", payload={"supplier_id": "SUP-001"},
                                                  prior_outputs={"R2": {"score": 0.9, "confidence": 0.8, "supplier_id": "SUP-001", "on_time_rate": 0.8, "fill_rate": 1, "defect_rate": 0, "invoice_accuracy": 1, "sample_size": 4}}))
    assert r3.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}, "SUP-001 fixture is MEDIUM lead-time risk"
    assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r3.output_id, "recommendation_id") is None
    alerts = [e for e in repo.list(COLLECTION_SYSTEM_EVENTS)
              if e["event_type"] == events.EVENT_EVIDENCE_RISK_ELEVATED and e["payload"].get("output_id") == r3.output_id]
    assert len(alerts) == 1
    assert alerts[0]["payload"]["agent_id"] == "R3"


@pytest.mark.asyncio
async def test_r4_consumes_evidence_normally_after_split(repo):
    """R1–R3 living only in outputs/state must not stop R4 from recommending."""
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert r4.action_type == "PurchaseRecommendation"
    assert r4.status.value == "READY_FOR_REVIEW"
    assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r4.recommendation_id, "recommendation_id")
    # Only R4's action is a review item — nothing from R1–R3 for this product/supplier.
    recs = repo.list(COLLECTION_AGENT_RECOMMENDATIONS)
    assert {r["agent_id"] for r in recs} == {"R4"}


# ---------------------------------------------------------------------------
# R5: evidence vs derived human action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r5_clean_match_creates_no_recommendation_and_closes_directly(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-001", "tester")
    assert r5.action["match_status"] == "MATCH"
    assert r5.action_recommendation_id is None
    assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r5.output_id, "recommendation_id") is None
    assert repo.get(COLLECTION_AGENT_OUTPUTS, r5.output_id, "output_id")
    assert not [r for r in repo.list(COLLECTION_AGENT_RECOMMENDATIONS) if r.get("action_type") == "ReconciliationReview"]

    closed = coord.close_purchase_order("PO-DEMO-001", r5.output_id, "mgr")
    assert closed["purchase_order"]["status"] == "CLOSED"
    assert repo.get(COLLECTION_OUTCOMES, "OUT-PO-DEMO-001", "outcome_id")


@pytest.mark.asyncio
async def test_r5_mismatch_publishes_evidence_and_raises_separate_review_action(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-002", "tester")
    assert r5.action["match_status"] == "MISMATCH"

    # Evidence: published, not a review item.
    assert repo.get(COLLECTION_AGENT_OUTPUTS, r5.output_id, "output_id")
    assert repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r5.output_id, "recommendation_id") is None
    # Signal: exception event.
    assert any(e["event_type"] == events.EVENT_EXCEPTION_CREATED and e["payload"]["output_id"] == r5.output_id
               for e in repo.list(COLLECTION_SYSTEM_EVENTS))
    # Action: exactly one derived review, linked both ways.
    review = repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r5.action_recommendation_id, "recommendation_id")
    assert review["action_type"] == "ReconciliationReview"
    assert review["source_output_id"] == r5.output_id
    assert review["status"] == "READY_FOR_REVIEW"
    assert review["action"]["proposed_action"] == "ACCEPT_AND_CLOSE"
    assert r5.output_id in review["input_refs"]
    # The review is itself a published contract with the full envelope.
    assert repo.get(COLLECTION_AGENT_OUTPUTS, review["output_id"], "output_id")["output_type"] == "ReconciliationReview"


@pytest.mark.asyncio
async def test_r5_mismatch_cannot_close_until_review_is_accepted(repo):
    from fastapi import HTTPException

    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-002", "tester")

    with pytest.raises(HTTPException) as exc:
        coord.close_purchase_order("PO-DEMO-002", r5.output_id, "mgr")
    assert exc.value.status_code == 409

    ApprovalService(repo).decide(r5.action_recommendation_id, ApprovalDecision(decision="REJECTED", reason="dispute"), "mgr")
    with pytest.raises(HTTPException):
        coord.close_purchase_order("PO-DEMO-002", r5.output_id, "mgr")

    # A fresh reconciliation yields a fresh review; approve that one and close.
    r5b = await coord.reconcile("PO-DEMO-002", "tester")
    assert r5b.action_recommendation_id != r5.action_recommendation_id
    ApprovalService(repo).decide(r5b.action_recommendation_id, ApprovalDecision(decision="APPROVED", reason="accepted"), "mgr")
    closed = coord.close_purchase_order("PO-DEMO-002", r5b.output_id, "mgr")
    assert closed["purchase_order"]["status"] == "CLOSED"
    assert closed["outcome"]["exception_count"] == 5


@pytest.mark.asyncio
async def test_repeated_reconciliation_reuses_review_for_same_output(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-002", "tester")
    again = coord._raise_reconciliation_review(r5, "tester")
    assert again.recommendation_id == r5.action_recommendation_id
    reviews = [r for r in repo.list(COLLECTION_AGENT_RECOMMENDATIONS) if r.get("source_output_id") == r5.output_id]
    assert len(reviews) == 1


# ---------------------------------------------------------------------------
# system_events are triggers; audit history is composed on read
# ---------------------------------------------------------------------------


def test_system_events_carry_no_bookkeeping_records():
    """Imports, upserts and bootstrap are not triggers and must not appear."""
    with TestClient(app) as client:
        client.post("/api/v1/demo/bootstrap")
        client.put("/api/v1/data/suppliers", json={"supplier_id": "SUP-EVT", "name": "Event Co", "status": "ACTIVE"})
        types = {e["event_type"] for e in client.get("/api/v1/events").json()}
        assert not any(t.startswith(("data.", "demo.", "job.")) for t in types), types
        from app.data.factory import get_repository
        get_repository().delete("suppliers", "SUP-EVT", "supplier_id")


# ---------------------------------------------------------------------------
# Blueprint p13 / Firebase p8: the exact trigger names other domains subscribe to
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("decision,expected", [
    ("APPROVED", events.EVENT_RECOMMENDATION_APPROVED),
    ("MODIFIED", events.EVENT_RECOMMENDATION_MODIFIED),
    ("REJECTED", events.EVENT_RECOMMENDATION_REJECTED),
])
@pytest.mark.asyncio
async def test_decision_emits_the_blueprint_named_event(repo, decision, expected):
    """Blueprint p13 names `recommendation.approved` as the trigger, so a
    consumer must be able to subscribe by event_type without reading payloads."""
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    payload = {"decision": decision, "reason": "audit"}
    if decision == "MODIFIED":
        payload["modified_action"] = {"qty": r4.action["qty"] - 5}
    ApprovalService(repo).decide(r4.recommendation_id, ApprovalDecision(**payload), "mgr")

    types = {e["event_type"] for e in repo.list(COLLECTION_SYSTEM_EVENTS)}
    assert expected in types
    assert "recommendation.decision" not in types, "the generic name is not a Blueprint trigger"


@pytest.mark.asyncio
async def test_outcome_recorded_event_is_emitted_for_evaluators(repo):
    """Blueprint p13: outcome.recorded → D5 + domain evaluators."""
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-001", "tester")
    coord.close_purchase_order("PO-DEMO-001", r5.output_id, "mgr")

    recorded = [e for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["event_type"] == events.EVENT_OUTCOME_RECORDED]
    assert len(recorded) == 1
    payload = recorded[0]["payload"]
    assert payload["outcome_id"] == "OUT-PO-DEMO-001"
    assert payload["reconciliation_status"] == "MATCH"
    assert "fill_rate" in payload and "price_variance" in payload


@pytest.mark.asyncio
async def test_r3_emits_supplier_performance_updated_only_when_risk_band_changes(repo):
    """Firebase p8 assigns this emission to R3 'when changed'.

    The change guard is load-bearing: Blueprint p13 also lists R2/R3 as
    consumers of this event, so an unconditional emit would form a cycle.
    """
    coord = ProcurementCoordinator(repo)

    def ctx():
        return AgentContext(entity_type="supplier", entity_id="SUP-001", payload={"supplier_id": "SUP-001"})

    def emitted():
        return [e for e in repo.list(COLLECTION_SYSTEM_EVENTS)
                if e["event_type"] == events.EVENT_SUPPLIER_PERFORMANCE_UPDATED and e["entity_id"] == "SUP-001"]

    first = await coord.run_agent("R3", ctx())
    assert not emitted(), "no prior state means no change to report"

    again = await coord.run_agent("R3", ctx())
    assert again.action["risk"] == first.action["risk"]
    assert not emitted(), "an unchanged risk band must stay silent — this is what prevents a cycle"

    # Degrade the supplier's delivery history so the band actually moves.
    for row in repo.list("supplier_performance"):
        if row["supplier_id"] == "SUP-001":
            repo.delete("supplier_performance", row["performance_id"], "performance_id")
    for i in range(4):
        repo.append("supplier_performance", {
            "performance_id": f"PERF-LATE-{i}", "supplier_id": "SUP-001", "po_id": f"PO-LATE-{i}",
            "order_date": "2026-08-01", "promised_date": "2026-08-06", "actual_date": "2026-08-27",
            "ordered_qty": 100, "received_qty": 100, "defect_qty": 0, "invoice_variance_pct": 0,
        })

    changed = await coord.run_agent("R3", ctx())
    assert changed.action["risk"] != first.action["risk"]
    signals = emitted()
    assert len(signals) == 1
    assert signals[0]["payload"]["previous_risk"] == first.action["risk"]
    assert signals[0]["payload"]["risk"] == changed.action["risk"]
    assert signals[0]["producer_agent"] == "R3"


# ---------------------------------------------------------------------------
# Blueprint p16 acceptance: "PO logic respects MOQ/lead time"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_raises_quantity_to_supplier_moq(repo):
    """A reorder smaller than the chosen supplier's MOQ must be raised to it."""
    outputs = OutputRepository(repo)
    reorder = outputs.get_latest_output("ReorderNeed", "SKU-100")
    outputs.seed_upstream_contract(
        "I2", "SKU-100", {**reorder.payload, "recommended_qty": 5},
        generated_at=datetime.now(timezone.utc),
    )

    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")

    quote = next(q for q in repo.list("supplier_quotes")
                 if q["supplier_id"] == r4.action["supplier_id"] and q["product_id"] == "SKU-100")
    assert r4.action["qty"] == float(quote["moq"]), "quantity must be raised to the supplier's MOQ"
    assert r4.action["qty"] > 5
    assert "quantity_raised_to_moq" in r4.guardrails


@pytest.mark.asyncio
async def test_r4_eta_comes_from_lead_time_risk_not_quoted_days(repo):
    """Blueprint p10: R3 estimates realistic lead time, 'not just quoted'."""
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    supplier = r4.action["supplier_id"]
    lead = OutputRepository(repo).get_latest_output("LeadTimeRisk", supplier)
    assert r4.action["eta_days"] == lead.payload["p90_days"]


@pytest.mark.asyncio
async def test_audit_history_reconstructs_full_lifecycle_without_audit_collection(repo):
    from app.services.audit_history import build_audit_history

    coord = ProcurementCoordinator(repo)
    r4 = await coord.recommend_purchase("SKU-100", "tester")
    ApprovalService(repo).decide(r4.recommendation_id, ApprovalDecision(decision="APPROVED", reason="ok"), "mgr")
    po = coord.execute_purchase_recommendation(r4.recommendation_id, "mgr")
    po_id = po["po_id"]
    repo.upsert("goods_receipts", {"receipt_id": f"GR-{po_id}", "po_id": po_id, "supplier_id": po["supplier_id"], "product_id": "SKU-100",
                                   "qty_received": po["qty"], "qty_defective": 0, "received_at": po["promised_date"] + "T10:00:00Z"}, "receipt_id")
    repo.upsert("invoices", {"invoice_id": f"INV-{po_id}", "invoice_number": f"N-{po_id}", "po_id": po_id, "supplier_id": po["supplier_id"],
                             "product_id": "SKU-100", "qty_invoiced": po["qty"], "unit_cost": po["unit_cost"], "tax_amount": 0,
                             "currency": "ZAR", "invoiced_at": po["promised_date"] + "T12:00:00Z"}, "invoice_id")
    r5 = await coord.reconcile(po_id, "tester")
    coord.close_purchase_order(po_id, r5.output_id, "mgr")

    assert "audit_events" not in repo._data, "no standalone audit collection may exist"

    history = build_audit_history(repo)
    types = [h["event_type"] for h in history]
    sources = {h["source"] for h in history}
    # Every stage of the lifecycle is present, drawn from six distinct canonical sources.
    assert "recommendation.raised.PurchaseRecommendation" in types      # generated
    assert "recommendation.approved" in types                            # reviewed/approved
    assert events.EVENT_PURCHASE_ORDER_CREATED in types                  # PO created
    assert events.EVENT_RECONCILIATION_COMPLETED in types                # reconciled
    assert "outcome.recorded" in types                                   # outcome
    assert events.EVENT_RECOMMENDATION_APPROVED in types                 # approved
    assert "agent.run.succeeded" in types
    assert "output.published.PurchaseRecommendation" in types
    assert sources == {"agent_runs", "agent_outputs", "agent_recommendations", "approval_log", "system_events", "outcomes"}
    # Newest first, and every row has the columns the Audit UI renders.
    assert history == sorted(history, key=lambda h: h["created_at"], reverse=True)
    assert all({"event_id", "created_at", "event_type", "entity_type", "entity_id", "actor_id"} <= set(h) for h in history)
    # Entity filter narrows to one PO's story.
    po_story = build_audit_history(repo, entity_id=po_id)
    assert po_story and all(po_id in (h["entity_id"], str(h["payload"])) for h in po_story)


# ---------------------------------------------------------------------------
# Upstream fixtures are DEV/TEST only
# ---------------------------------------------------------------------------


def test_upstream_seeding_is_refused_in_shared_mode(repo, monkeypatch):
    from app.core import config
    from app.data import output_repository as orm

    monkeypatch.setattr(orm, "get_settings", lambda: config.Settings(allow_upstream_fixtures=False))
    with pytest.raises(OwnershipViolation, match="not the producer"):
        OutputRepository(repo).seed_upstream_contract("I2", "SKU-100", {"product_id": "SKU-100", "reorder_point": 1,
                                                                        "projected_position": 0, "reorder_needed": True, "recommended_qty": 5})


def test_upstream_import_endpoint_is_refused_in_shared_mode(monkeypatch):
    from app.api import routes
    from app.core import config

    monkeypatch.setattr(routes, "get_settings", lambda: config.Settings(allow_upstream_fixtures=False))
    with TestClient(app) as client:
        r = client.post("/api/v1/imports/reorder_needs", files={"file": ("x.csv", b"product_id,reorder_point,projected_position,reorder_needed,recommended_qty\nSKU-100,1,0,true,5\n", "text/csv")})
        assert r.status_code == 403
        assert "owning domain" in r.json()["detail"] and "not by procurement" in r.json()["detail"].lower()
        # Operational imports are unaffected.
        ok = client.post("/api/v1/imports/suppliers", files={"file": ("s.csv", b"supplier_id,name,status\nSUP-SHARED,Shared Co,ACTIVE\n", "text/csv")})
        assert ok.status_code == 200
        from app.data.factory import get_repository
        get_repository().delete("suppliers", "SUP-SHARED", "supplier_id")


def test_bootstrap_skips_upstream_fixtures_in_shared_mode(repo, monkeypatch):
    from app.core import config
    from app.data import bootstrap as bs

    monkeypatch.setattr(bs, "get_settings", lambda: config.Settings(allow_upstream_fixtures=False))
    for row in list(repo.list(COLLECTION_AGENT_STATE)):
        repo.delete(COLLECTION_AGENT_STATE, row["state_id"], "state_id")
    summary = bs.bootstrap_sample_data(repo)
    assert "skipped" in str(summary.get("agent_state", ""))
    assert OutputRepository(repo).get_latest_output("ReorderNeed", "SKU-100") is None
    assert repo.list("suppliers"), "operational data still loads"


@pytest.mark.asyncio
async def test_r4_consumes_upstream_from_shared_state_and_publishes_everywhere(repo):
    outputs = OutputRepository(repo)
    for t in ("ReorderNeed", "SafetyStockTarget", "DemandForecast"):
        assert outputs.get_latest_output(t, "SKU-100"), f"{t} must be seeded into agent_state"

    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert r4.action_type == "PurchaseRecommendation"

    assert repo.get(COLLECTION_AGENT_OUTPUTS, r4.output_id, "output_id")
    assert repo.get(COLLECTION_AGENT_STATE, state_id("R4", "PurchaseRecommendation", "SKU-100"), "state_id")
    rec = repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r4.recommendation_id, "recommendation_id")
    assert rec and rec["source_output_id"] == r4.output_id
    assert rec["domain"] == "procurement" and rec["schema_version"] == SCHEMA_VERSION

    created = [e for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["event_type"] == events.EVENT_PURCHASE_RECOMMENDATION_CREATED]
    assert created and created[-1]["payload"]["recommendation_id"] == r4.recommendation_id


@pytest.mark.asyncio
async def test_r4_input_refs_identify_exact_upstream_output_ids(repo):
    outputs = OutputRepository(repo)
    expected = {outputs.get_latest_output(t, "SKU-100").output_id for t in ("ReorderNeed", "SafetyStockTarget", "DemandForecast")}
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert expected <= set(r4.input_refs), "R4 must reference the concrete I2/I3/D4 output ids it consumed"
    assert any(ref.startswith("REC-") for ref in r4.input_refs), "R4 must reference the R1/R2/R3 output ids"


@pytest.mark.asyncio
async def test_r4_fails_safe_when_upstream_state_absent(repo):
    for t in ("ReorderNeed", "SafetyStockTarget", "DemandForecast"):
        for row in repo.list(COLLECTION_AGENT_STATE):
            if row["output_type"] == t and row["entity_id"] == "SKU-100":
                repo.delete(COLLECTION_AGENT_STATE, row["state_id"], "state_id")
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert r4.status.value == "DRAFT"
    assert "insufficient_evidence" in r4.guardrails
    assert not r4.action, "no supplier selection may be fabricated"


@pytest.mark.asyncio
async def test_r4_does_not_consume_expired_upstream_state(repo):
    outputs = OutputRepository(repo)
    current = outputs.get_latest_output("ReorderNeed", "SKU-100")
    repo.upsert(COLLECTION_AGENT_STATE, {
        **current.model_dump(mode="json"),
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    }, "state_id")
    assert outputs.get_latest_output("ReorderNeed", "SKU-100") is None


# ---------------------------------------------------------------------------
# agent_runs trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_run_leaves_a_completed_trace(repo):
    r4 = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    runs = repo.list(COLLECTION_AGENT_RUNS)
    assert {r["agent_id"] for r in runs} >= {"R1", "R2", "R3", "R4"}
    r4_run = repo.get(COLLECTION_AGENT_RUNS, r4.run_id, "run_id")
    assert r4_run["status"] == "SUCCEEDED"
    assert r4_run["output_id"] == r4.output_id
    assert r4_run["completed_at"] and r4_run["duration_ms"] is not None
    assert r4_run["model_or_rule_version"] == "1.0.0-r4"
    assert r4_run["schema_version"] == SCHEMA_VERSION
    assert set(r4_run["input_refs"]) == set(r4.input_refs)


@pytest.mark.asyncio
async def test_failed_run_records_error_summary_without_internals(repo, monkeypatch):
    coord = ProcurementCoordinator(repo)

    async def boom(context):
        raise RuntimeError("secret-token=abc123 " + "x" * 2000)

    monkeypatch.setattr(coord.agents["R1"], "run", boom)
    with pytest.raises(RuntimeError):
        await coord.run_agent("R1", AgentContext(entity_type="product", entity_id="SKU-100"))
    failed = [r for r in repo.list(COLLECTION_AGENT_RUNS) if r["status"] == "FAILED"]
    assert failed
    assert len(failed[0]["error"]) <= 500, "error summary must be bounded"


# ---------------------------------------------------------------------------
# approval_log / execution / outcomes / events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_journals_and_events_are_idempotent(repo):
    coord = ProcurementCoordinator(repo)
    r4 = await coord.recommend_purchase("SKU-100", "tester")
    ApprovalService(repo).decide(r4.recommendation_id, ApprovalDecision(decision="APPROVED", reason="ok"), "mgr")

    log = [a for a in repo.list(COLLECTION_APPROVAL_LOG) if a["recommendation_id"] == r4.recommendation_id]
    assert len(log) == 1 and log[0]["reviewer"] == "mgr" and log[0]["schema_version"] == SCHEMA_VERSION

    po1 = coord.execute_purchase_recommendation(r4.recommendation_id, "mgr")
    po2 = coord.execute_purchase_recommendation(r4.recommendation_id, "mgr")
    assert po1["po_id"] == po2["po_id"]
    created = [e for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["event_type"] == events.EVENT_PURCHASE_ORDER_CREATED and e["entity_id"] == po1["po_id"]]
    assert len(created) == 1, "retried execution must not duplicate the created event"


def test_deterministic_event_id_makes_retry_a_noop(repo):
    for _ in range(3):
        events.publish_event(repo, "goods.receipt.recorded", "purchase_order", "PO-X", "sys", {"receipt_id": "GR-1"}, idempotency_key="GR-1")
    assert len([e for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["entity_id"] == "PO-X"]) == 1


@pytest.mark.asyncio
async def test_close_writes_outcome_referencing_supplier_performance(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-001", "tester")
    result = coord.close_purchase_order("PO-DEMO-001", r5.recommendation_id, "mgr")

    outcome = repo.get(COLLECTION_OUTCOMES, "OUT-PO-DEMO-001", "outcome_id")
    assert outcome
    assert outcome["performance_id"] == result["supplier_performance"]["performance_id"]
    assert outcome["reconciliation_status"] == "MATCH"
    assert outcome["exception_count"] == 0
    assert 0 <= outcome["fill_rate"] <= 1

    types = {e["event_type"] for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["entity_id"] in {"PO-DEMO-001", "SUP-002"}}
    assert events.EVENT_PURCHASE_ORDER_CLOSED in types
    assert events.EVENT_SUPPLIER_PERFORMANCE_UPDATED in types


@pytest.mark.asyncio
async def test_repeated_close_does_not_duplicate_outcome(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-001", "tester")
    coord.close_purchase_order("PO-DEMO-001", r5.recommendation_id, "mgr")
    coord.close_purchase_order("PO-DEMO-001", r5.recommendation_id, "mgr")
    assert len([o for o in repo.list(COLLECTION_OUTCOMES) if o["purchase_order_id"] == "PO-DEMO-001"]) == 1
    assert len([p for p in repo.list("supplier_performance") if p["po_id"] == "PO-DEMO-001"]) == 1


@pytest.mark.asyncio
async def test_r5_mismatch_emits_exception_event(repo):
    coord = ProcurementCoordinator(repo)
    r5 = await coord.reconcile("PO-DEMO-002", "tester")
    assert r5.action["match_status"] == "MISMATCH"
    ev = [e for e in repo.list(COLLECTION_SYSTEM_EVENTS) if e["event_type"] == events.EVENT_EXCEPTION_CREATED and e["entity_id"] == "PO-DEMO-002"]
    assert ev and "UNDER_DELIVERY" in ev[0]["payload"]["exception_types"]


@pytest.mark.asyncio
async def test_repeated_reconciliation_is_safe(repo):
    coord = ProcurementCoordinator(repo)
    a = await coord.reconcile("PO-DEMO-002", "tester")
    b = await coord.reconcile("PO-DEMO-002", "tester")
    assert a.action["match_status"] == b.action["match_status"]
    state = repo.get(COLLECTION_AGENT_STATE, state_id("R5", "ProcurementException", "PO-DEMO-002"), "state_id")
    assert state["output_id"] == b.output_id, "state must reflect the most recent reconciliation"


# ---------------------------------------------------------------------------
# End-to-end trace reconstruction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_input_to_output_trace_can_be_reconstructed(repo):
    coord = ProcurementCoordinator(repo)
    r4 = await coord.recommend_purchase("SKU-100", "tester")
    ApprovalService(repo).decide(r4.recommendation_id, ApprovalDecision(decision="APPROVED", reason="ok"), "mgr")
    po = coord.execute_purchase_recommendation(r4.recommendation_id, "mgr")

    # Walk the graph purely from persisted records.
    r4_out = repo.get(COLLECTION_AGENT_OUTPUTS, r4.output_id, "output_id")
    run = repo.get(COLLECTION_AGENT_RUNS, r4_out["run_id"], "run_id")
    assert run["agent_id"] == "R4"
    for ref in r4_out["input_refs"]:
        if ref.startswith(("REC-", "I2-", "I3-", "D4-")):
            assert repo.get(COLLECTION_AGENT_OUTPUTS, ref, "output_id"), f"input ref {ref} is not resolvable"
    rec = repo.get(COLLECTION_AGENT_RECOMMENDATIONS, r4.recommendation_id, "recommendation_id")
    assert rec["source_output_id"] == r4.output_id
    log = [a for a in repo.list(COLLECTION_APPROVAL_LOG) if a["recommendation_id"] == r4.recommendation_id]
    assert log
    assert repo.get("purchase_orders", po["po_id"], "po_id")["recommendation_id"] == r4.recommendation_id


# ---------------------------------------------------------------------------
# HTTP surface: protected collections are read-only for clients
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("collection", sorted(PROTECTED_COLLECTIONS))
def test_protected_collections_cannot_be_written_via_api(collection):
    with TestClient(app) as client:
        response = client.put(f"/api/v1/data/{collection}", json={"x": 1})
        assert response.status_code == 404, f"{collection} must not be client-writable"
        assert client.get(f"/api/v1/data/{collection}").status_code == 200


def test_latest_output_endpoint_serves_shared_state():
    with TestClient(app) as client:
        r = client.get("/api/v1/outputs/ReorderNeed/SKU-100")
        assert r.status_code == 200
        body = r.json()
        assert body["agent_id"] == "I2" and body["domain"] == "inventory"
        assert client.get("/api/v1/outputs/ReorderNeed/SKU-NOPE").status_code == 404
