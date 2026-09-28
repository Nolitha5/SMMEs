from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.agents.procurement.registry import AGENT_CLASSES
from app.contracts.models import (
    AgentContext, AgentResult, DemandForecast, PurchaseOrder, ReorderNeed, RiskLevel, SafetyStockTarget,
)
from app.contracts.shared import (
    COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_OUTCOMES,
    EVIDENCE_OUTPUT_TYPES, Outcome, SharedAgentOutput,
)
from app.data.output_repository import OutputRepository
from app.data.repository import Repository
from app.governance.policies import can_execute
from app.services import events
from app.services.runs import finish_run, latest_run_per_agent, start_run


class ProcurementCoordinator:
    """Lightweight coordinator: routes dependencies and publishes outputs; domain logic stays inside R1–R5."""

    def __init__(self, repo: Repository):
        self.repo = repo
        self.outputs = OutputRepository(repo)
        self.agents = {agent_id: cls(repo) for agent_id, cls in AGENT_CLASSES.items()}

    # ------------------------------------------------------------------
    # Execution with run trace + shared publication
    # ------------------------------------------------------------------

    async def run_agent(self, agent_id: str, context: AgentContext, persist: bool = True) -> AgentResult:
        if agent_id not in self.agents:
            raise HTTPException(status_code=404, detail=f"Unknown procurement agent {agent_id}")
        agent = self.agents[agent_id]
        # Captured before the run so a change can be detected after publication.
        prior_r3 = (
            self.outputs.get_latest_output("LeadTimeRisk", context.entity_id, agent_id="R3")
            if agent_id == "R3" else None
        )
        run = start_run(
            self.repo, agent_id, context.entity_type, context.entity_id,
            agent.version, actor_id=context.actor_id, input_refs=context.input_refs,
        )
        context.run_id = run.run_id
        try:
            result = await agent.run(context)
        except Exception as exc:
            finish_run(self.repo, run, error=f"{type(exc).__name__}: {exc}")
            raise
        if persist:
            self.outputs.publish(result)
            # Firebase architecture p8: R3 emits supplier.performance.updated
            # "when changed". Gating on an actual change in the published risk
            # band is what makes this safe — the Blueprint (p13) also lists
            # R2/R3 as *consumers* of this event, so an unconditional emit would
            # form a cycle. A re-run with an unchanged band emits nothing.
            if agent_id == "R3":
                previous = (prior_r3.payload.get("risk") if prior_r3 else None)
                current = (result.action or {}).get("risk")
                if previous is not None and current != previous:
                    events.publish_event(
                        self.repo, events.EVENT_SUPPLIER_PERFORMANCE_UPDATED, "supplier", result.entity_id,
                        context.actor_id,
                        {"output_id": result.output_id, "previous_risk": previous, "risk": current,
                         "expected_days": (result.action or {}).get("expected_days"),
                         "p90_days": (result.action or {}).get("p90_days"), "reason": "lead_time_risk_changed"},
                        producer_agent="R3", idempotency_key=result.output_id,
                    )
            # Elevated risk on an evidence contract is an operational signal,
            # not a review item: raise an event for whoever needs to react.
            if result.action_type in EVIDENCE_OUTPUT_TYPES and result.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH} \
                    and "insufficient_evidence" not in result.guardrails:
                events.publish_event(
                    self.repo, events.EVENT_EVIDENCE_RISK_ELEVATED, result.entity_type, result.entity_id,
                    context.actor_id,
                    {"agent_id": agent_id, "output_id": result.output_id, "output_type": result.action_type,
                     "risk_level": result.risk_level.value, "guardrails": list(result.guardrails)},
                    producer_agent=agent_id, idempotency_key=result.output_id,
                )
        finish_run(self.repo, run, output_id=result.output_id, input_refs=result.input_refs)
        return result

    # ------------------------------------------------------------------
    # Upstream contract consumption (never fabricated)
    # ------------------------------------------------------------------

    def _upstream(self, output_type: str, product_id: str, payload_model) -> SharedAgentOutput | None:
        """Latest schema-valid, unexpired upstream state.

        Freshness is deliberately *not* filtered here: R4 applies the 72-hour
        Procurement policy itself and reports `stale_dependency` precisely,
        which is more useful to a reviewer than "missing". The repository still
        enforces the hard floor — schema validity and `expires_at`.
        """
        return self.outputs.get_latest_output(output_type, product_id, payload_model=payload_model)

    async def recommend_purchase(self, product_id: str, actor_id: str = "system") -> AgentResult:
        reorder = self._upstream("ReorderNeed", product_id, ReorderNeed)
        safety = self._upstream("SafetyStockTarget", product_id, SafetyStockTarget)
        forecast = self._upstream("DemandForecast", product_id, DemandForecast)

        upstream_refs = [e.output_id for e in (reorder, safety, forecast) if e]
        requested_qty = float((reorder.payload if reorder else {}).get("recommended_qty", 1) or 1)

        r1 = await self.run_agent("R1", AgentContext(
            entity_type="product", entity_id=product_id,
            payload={"requested_qty": requested_qty}, actor_id=actor_id,
        ))
        comparison = r1.action
        r2_outputs, r3_outputs, supplier_refs = {}, {}, []
        for candidate in comparison.get("ranked_suppliers", []):
            supplier_id = candidate["supplier_id"]
            r2 = await self.run_agent("R2", AgentContext(
                entity_type="supplier", entity_id=supplier_id,
                payload={"supplier_id": supplier_id}, actor_id=actor_id,
            ))
            r3 = await self.run_agent("R3", AgentContext(
                entity_type="supplier", entity_id=supplier_id, payload={"supplier_id": supplier_id},
                prior_outputs={"R2": r2.action}, actor_id=actor_id, input_refs=[r2.output_id],
            ))
            r2_outputs[supplier_id] = r2.action
            r3_outputs[supplier_id] = r3.action
            supplier_refs.extend([r2.output_id, r3.output_id])

        prior = {
            "R1": r1.action, "R2": r2_outputs, "R3": r3_outputs,
            **({"I2": reorder.payload} if reorder else {}),
            **({"I3": safety.payload} if safety else {}),
            **({"D4": forecast.payload} if forecast else {}),
        }
        r4 = await self.run_agent("R4", AgentContext(
            entity_type="product", entity_id=product_id, payload={}, prior_outputs=prior, actor_id=actor_id,
            input_refs=[*upstream_refs, r1.output_id, *supplier_refs],
        ))

        if r4.action_type == "PurchaseRecommendation" and r4.action:
            events.publish_event(
                self.repo, events.EVENT_PURCHASE_RECOMMENDATION_CREATED, "product", product_id, actor_id,
                {"recommendation_id": r4.recommendation_id, "output_id": r4.output_id,
                 "upstream_output_ids": upstream_refs, "r1_output_id": r1.output_id},
                producer_agent="R4", idempotency_key=r4.output_id,
            )
        return r4

    # ------------------------------------------------------------------
    # R5 reconciliation
    # ------------------------------------------------------------------

    async def reconcile(self, po_id: str, actor_id: str = "system") -> AgentResult:
        po = self.repo.get("purchase_orders", po_id, "po_id")
        refs = []
        if po:
            refs.append(f"purchase_orders:{po_id}")
            if po.get("recommendation_id"):
                refs.append(po["recommendation_id"])
        result = await self.run_agent("R5", AgentContext(
            entity_type="purchase_order", entity_id=po_id, payload={"po_id": po_id},
            actor_id=actor_id, input_refs=refs,
        ))
        action = result.action or {}
        match_status = action.get("match_status")
        events.publish_event(
            self.repo, events.EVENT_RECONCILIATION_COMPLETED, "purchase_order", po_id, actor_id,
            {"output_id": result.output_id, "match_status": match_status},
            producer_agent="R5", idempotency_key=result.output_id,
        )

        exception_types = action.get("exception_types") or []
        if exception_types and "INSUFFICIENT_EVIDENCE" not in exception_types:
            # 1. R5 detected an exception — an operational signal.
            events.publish_event(
                self.repo, events.EVENT_EXCEPTION_CREATED, "purchase_order", po_id, actor_id,
                {"output_id": result.output_id, "exception_types": exception_types,
                 "severity": result.risk_level.value},
                producer_agent="R5", idempotency_key=result.output_id,
            )
            # 2. Separately: a human must now decide whether to accept the
            #    exceptions and close the PO. That decision is the action
            #    recommendation; the R5 output above is only the evidence.
            review = self._raise_reconciliation_review(result, actor_id)
            result.action_recommendation_id = review.recommendation_id
        return result

    def _raise_reconciliation_review(self, r5: AgentResult, actor_id: str) -> AgentResult:
        """Create the ReconciliationReview action derived from an R5 mismatch.

        Idempotent per R5 output: re-running reconciliation for the same PO
        produces a new R5 output and therefore a new review; the previous one
        remains in history with its own source_output_id.
        """
        existing = next(
            (r for r in self.repo.list(COLLECTION_AGENT_RECOMMENDATIONS)
             if r.get("action_type") == "ReconciliationReview" and r.get("source_output_id") == r5.output_id),
            None,
        )
        if existing:
            return AgentResult.model_validate(existing)

        action = r5.action or {}
        ctx = AgentContext(
            entity_type="purchase_order", entity_id=r5.entity_id, actor_id=actor_id,
            payload={"po_id": r5.entity_id}, input_refs=[r5.output_id, *r5.input_refs], run_id=r5.run_id,
        )
        review = self.agents["R5"].result(
            ctx, "ReconciliationReview",
            {
                "po_id": r5.entity_id,
                "supplier_id": action.get("supplier_id"),
                "match_status": action.get("match_status"),
                "exception_types": list(action.get("exception_types") or []),
                "financial_variance": action.get("financial_variance", 0.0),
                "proposed_action": "ACCEPT_AND_CLOSE",
                "reconciliation_output_id": r5.output_id,
            },
            [
                f"R5 found {len(action.get('exception_types') or [])} reconciliation exception(s) on {r5.entity_id}: "
                f"{', '.join(action.get('exception_types') or [])}.",
                "A manager must accept, modify or reject closing this purchase order with these exceptions.",
            ],
            [f"R5:ProcurementException:{r5.output_id}"],
            r5.confidence, r5.risk_level, True, ["human_approval_required", "reconciliation_exception"],
        )
        review.source_output_id = r5.output_id
        self.outputs.publish(review)
        return review

    # ------------------------------------------------------------------
    # Purchase-order execution (only after human approval)
    # ------------------------------------------------------------------

    def execute_purchase_recommendation(self, recommendation_id: str, actor_id: str) -> dict:
        rec = self.repo.get(COLLECTION_AGENT_RECOMMENDATIONS, recommendation_id, "recommendation_id")
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        existing = self.repo.get("purchase_orders", recommendation_id, "recommendation_id")
        if existing:
            return existing
        ok, reason = can_execute(rec)
        if not ok:
            raise HTTPException(status_code=409, detail=reason)
        action = rec.get("action") or {}
        eta_days = max(int(round(float(action.get("eta_days", 1)))), 1)
        po = PurchaseOrder(
            po_id=f"PO-{uuid4().hex[:10].upper()}",
            recommendation_id=recommendation_id,
            supplier_id=action["supplier_id"],
            product_id=action["product_id"],
            qty=float(action["qty"]),
            unit_cost=float(action["unit_cost"]),
            currency=action.get("currency", "ZAR"),
            promised_date=date.today() + timedelta(days=eta_days),
            created_by=actor_id,
        )
        data = po.model_dump(mode="json")
        rec["status"] = "EXECUTED"
        rec["executed_po_id"] = po.po_id
        self.repo.write_batch([
            ("upsert", "purchase_orders", data, "po_id"),
            ("upsert", COLLECTION_AGENT_RECOMMENDATIONS, rec, "recommendation_id"),
        ])
        events.publish_event(
            self.repo, events.EVENT_PURCHASE_ORDER_CREATED, "purchase_order", po.po_id, actor_id,
            {"recommendation_id": recommendation_id, "supplier_id": po.supplier_id,
             "product_id": po.product_id, "qty": po.qty, "promised_date": po.promised_date.isoformat()},
            producer_agent="R4", idempotency_key=recommendation_id,
        )
        return data

    # ------------------------------------------------------------------
    # PO closure → supplier_performance + outcomes (feeds R2/R3)
    # ------------------------------------------------------------------

    def close_purchase_order(self, po_id: str, reconciliation_id: str, actor_id: str) -> dict:
        """Close a PO against an R5 reconciliation output.

        A clean MATCH is deterministic, low-risk evidence and closes directly.
        Any exception requires the derived ReconciliationReview action to have
        been approved or modified by a manager — the safety gate is unchanged,
        it now sits on the action rather than on the evidence.
        """
        r5 = self.repo.get(COLLECTION_AGENT_OUTPUTS, reconciliation_id, "output_id")
        if not r5 or r5.get("agent_id") != "R5" or r5.get("output_type") != "ProcurementException" \
                or r5.get("entity_id") != po_id:
            raise HTTPException(status_code=404, detail="R5 reconciliation output not found for this PO")
        r5_action = r5.get("payload") or {}
        match_status = r5_action.get("match_status")
        if match_status == "INSUFFICIENT_EVIDENCE":
            raise HTTPException(status_code=409, detail="Reconciliation had insufficient evidence; the purchase order cannot be closed")
        if match_status != "MATCH":
            review = next(
                (r for r in self.repo.list(COLLECTION_AGENT_RECOMMENDATIONS)
                 if r.get("action_type") == "ReconciliationReview" and r.get("source_output_id") == reconciliation_id),
                None,
            )
            if not review:
                raise HTTPException(status_code=409, detail="Reconciliation exceptions require a review action before closing")
            if review.get("status") not in {"APPROVED", "MODIFIED"}:
                raise HTTPException(status_code=409, detail="Reconciliation exceptions must be accepted before closing the purchase order")
        rec = {"action": r5_action, "output_id": reconciliation_id}
        po = self.repo.get("purchase_orders", po_id, "po_id")
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        receipts = [r for r in self.repo.list("goods_receipts") if str(r.get("po_id")) == po_id]
        invoices = [i for i in self.repo.list("invoices") if str(i.get("po_id")) == po_id]
        if not receipts or not invoices:
            raise HTTPException(status_code=409, detail="Receipt and invoice evidence are required before closing")
        from app.services.analytics import parse_datetime
        latest_receipt = max(parse_datetime(r["received_at"]) for r in receipts)
        ordered_qty = float(po["qty"])
        received_qty = sum(float(r.get("qty_received", 0)) for r in receipts)
        defect_qty = sum(float(r.get("qty_defective", 0)) for r in receipts)
        expected = ordered_qty * float(po["unit_cost"])
        invoiced = sum(float(i.get("qty_invoiced", 0)) * float(i.get("unit_cost", 0)) for i in invoices)
        variance_pct = (invoiced - expected) / expected if expected else 0.0
        promised = str(po["promised_date"])[:10]
        actual = latest_receipt.date().isoformat()

        existing = self.repo.get("supplier_performance", po_id, "po_id")
        performance = existing or {
            "performance_id": f"PERF-{uuid4().hex[:12].upper()}",
            "supplier_id": po["supplier_id"],
            "po_id": po_id,
            "order_date": str(po["ordered_at"])[:10],
            "promised_date": promised,
            "actual_date": actual,
            "ordered_qty": ordered_qty,
            "received_qty": received_qty,
            "defect_qty": defect_qty,
            "invoice_variance_pct": round(variance_pct, 6),
        }

        exception_types = (rec.get("action") or {}).get("exception_types") or []
        outcome = Outcome(
            outcome_id=f"OUT-{po_id}",
            recommendation_id=po.get("recommendation_id"),
            purchase_order_id=po_id,
            supplier_id=po["supplier_id"],
            product_id=po["product_id"],
            performance_id=performance["performance_id"],
            promised_date=promised,
            actual_date=actual,
            ordered_qty=ordered_qty,
            received_qty=received_qty,
            fill_rate=min(received_qty / ordered_qty, 1.0) if ordered_qty else 0.0,
            defect_rate=min(defect_qty / received_qty, 1.0) if received_qty else 0.0,
            price_variance=round(invoiced - expected, 2),
            delivery_variance_days=(date.fromisoformat(actual) - date.fromisoformat(promised)).days,
            reconciliation_status=str((rec.get("action") or {}).get("match_status", "UNKNOWN")),
            exception_count=len(exception_types),
            reconciliation_output_id=rec.get("output_id") or reconciliation_id,
        )

        po["status"] = "CLOSED"
        self.repo.write_batch([
            ("upsert", "supplier_performance", performance, "performance_id"),
            ("insert_if_absent", COLLECTION_OUTCOMES, outcome.model_dump(mode="json"), "outcome_id"),
            ("upsert", "purchase_orders", po, "po_id"),
        ])
        events.publish_event(
            self.repo, events.EVENT_PURCHASE_ORDER_CLOSED, "purchase_order", po_id, actor_id,
            {"reconciliation_id": reconciliation_id, "performance_id": performance["performance_id"],
             "outcome_id": outcome.outcome_id},
            producer_agent="R5", idempotency_key=f"close:{po_id}",
        )
        # Blueprint p13: outcome.recorded → D5 and domain evaluators compare the
        # recommendation's expectation against the actual result.
        events.publish_event(
            self.repo, events.EVENT_OUTCOME_RECORDED, "purchase_order", po_id, actor_id,
            {"outcome_id": outcome.outcome_id, "recommendation_id": outcome.recommendation_id,
             "supplier_id": outcome.supplier_id, "product_id": outcome.product_id,
             "reconciliation_status": outcome.reconciliation_status, "fill_rate": outcome.fill_rate,
             "price_variance": outcome.price_variance, "delivery_variance_days": outcome.delivery_variance_days},
            producer_agent="R5", idempotency_key=outcome.outcome_id,
        )
        # Signal the shared layer that reliability/lead-time evidence changed,
        # so R2/R3 (and any Inventory consumer) can re-evaluate without a direct call.
        events.publish_event(
            self.repo, events.EVENT_SUPPLIER_PERFORMANCE_UPDATED, "supplier", po["supplier_id"], actor_id,
            {"performance_id": performance["performance_id"], "po_id": po_id, "outcome_id": outcome.outcome_id},
            producer_agent="R5", idempotency_key=performance["performance_id"],
        )
        return {"purchase_order": po, "supplier_performance": performance, "outcome": outcome.model_dump(mode="json")}

    # ------------------------------------------------------------------
    # Status view derived from agent_runs
    # ------------------------------------------------------------------

    def agent_statuses(self) -> list[dict]:
        latest = latest_run_per_agent(self.repo)
        out = []
        for agent_id, agent in self.agents.items():
            run = latest.get(agent_id)
            out.append({
                "agent_id": agent_id, "name": agent.name, "version": agent.version, "enabled": True,
                "last_run_at": (run or {}).get("completed_at") or (run or {}).get("started_at"),
                "last_error": (run or {}).get("error"),
                "last_run_id": (run or {}).get("run_id"),
            })
        return out
