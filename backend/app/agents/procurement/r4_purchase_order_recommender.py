from __future__ import annotations

from app.agents.base import BaseProcurementAgent
from app.contracts.models import (
    AgentContext, DemandForecast, LeadTimeRisk, PurchaseRecommendation, ReorderNeed,
    RiskLevel, SafetyStockTarget, SupplierComparison, SupplierReliabilityScore,
)
from app.governance.policies import second_review_required
from app.services.analytics import clamp
from app.services.data_quality import is_stale


class PurchaseOrderRecommenderAgent(BaseProcurementAgent):
    agent_id = "R4"
    name = "Purchase Order Recommender"
    version = "1.0.0-r4"

    async def run(self, context: AgentContext):
        missing = [k for k in ("I2", "I3", "D4", "R1", "R2", "R3") if k not in context.prior_outputs]
        if missing:
            return self.result(
                context, "PurchaseRecommendation", {},
                [f"Required upstream procurement inputs are missing: {', '.join(missing)}."],
                missing, 0.0, RiskLevel.HIGH, True, ["insufficient_evidence", "missing_dependencies"],
            )
        try:
            reorder = ReorderNeed.model_validate(context.prior_outputs["I2"])
            safety = SafetyStockTarget.model_validate(context.prior_outputs["I3"])
            forecast = DemandForecast.model_validate(context.prior_outputs["D4"])
            comparison = SupplierComparison.model_validate(context.prior_outputs["R1"])
        except Exception as exc:
            return self.result(
                context, "PurchaseRecommendation", {}, [f"Upstream contract validation failed: {exc}"],
                ["I2", "I3", "D4", "R1"], 0.0, RiskLevel.HIGH, True,
                ["insufficient_evidence", "contract_validation_failed"],
            )

        stale = []
        for name, value in (("I2", reorder.generated_at), ("I3", safety.generated_at), ("D4", forecast.generated_at)):
            if is_stale(value, 72):
                stale.append(name)
        if stale:
            return self.result(
                context, "PurchaseRecommendation", {},
                [f"Upstream decision evidence is stale: {', '.join(stale)}. A new purchase recommendation was not issued."],
                stale, 0.0, RiskLevel.HIGH, True, ["insufficient_evidence", "stale_dependency"],
            )
        if not reorder.reorder_needed or reorder.recommended_qty <= 0:
            return self.result(
                context, "NoPurchaseRequired",
                {"product_id": context.entity_id, "reorder_needed": False, "recommended_qty": 0},
                ["The external Inventory ReorderNeed contract indicates that no purchase is currently required."],
                ["I2"], 0.96, RiskLevel.LOW, False,
            )
        if not comparison.ranked_suppliers:
            return self.result(
                context, "PurchaseRecommendation", {},
                ["A reorder is required but R1 found no eligible supplier offer."], ["I2", "R1"], 0.0,
                RiskLevel.HIGH, True, ["insufficient_evidence", "no_eligible_supplier"],
            )

        reliability_map = {sid: SupplierReliabilityScore.model_validate(v) for sid, v in context.prior_outputs["R2"].items()}
        lead_map = {sid: LeadTimeRisk.model_validate(v) for sid, v in context.prior_outputs["R3"].items()}
        candidates = []
        for rank in comparison.ranked_suppliers:
            rel = reliability_map.get(rank.supplier_id)
            lead = lead_map.get(rank.supplier_id)
            if not rel or not lead:
                continue
            lead_score = {RiskLevel.LOW: 1.0, RiskLevel.MEDIUM: 0.6, RiskLevel.HIGH: 0.2}[lead.risk]
            evidence_conf = min(rel.confidence, lead.confidence, forecast.confidence)
            decision_score = clamp(0.40 * rank.score + 0.35 * rel.score + 0.20 * lead_score + 0.05 * evidence_conf)
            qty = max(reorder.recommended_qty, rank.moq)
            if any("available quantity" in w.lower() for w in rank.warnings):
                decision_score *= 0.75
            candidates.append({
                "rank": rank, "rel": rel, "lead": lead, "qty": qty,
                "expected_cost": qty * rank.unit_cost, "decision_score": decision_score,
            })
        if not candidates:
            return self.result(
                context, "PurchaseRecommendation", {},
                ["Supplier comparison exists, but reliability/lead-time contracts are incomplete for every candidate."],
                ["R1", "R2", "R3"], 0.0, RiskLevel.HIGH, True,
                ["insufficient_evidence", "supplier_evidence_incomplete"],
            )

        candidates.sort(key=lambda x: (x["decision_score"], -x["expected_cost"]), reverse=True)
        chosen = candidates[0]
        rank, rel, lead = chosen["rank"], chosen["rel"], chosen["lead"]
        risk = RiskLevel.LOW
        if lead.risk == RiskLevel.HIGH or rel.score < 0.55 or forecast.confidence < 0.45:
            risk = RiskLevel.HIGH
        elif lead.risk == RiskLevel.MEDIUM or rel.score < 0.75 or forecast.confidence < 0.70:
            risk = RiskLevel.MEDIUM
        if second_review_required(chosen["expected_cost"], risk):
            risk = RiskLevel.HIGH

        alternatives = [{
            "supplier_id": c["rank"].supplier_id,
            "qty": round(c["qty"], 2), "expected_cost": round(c["expected_cost"], 2),
            "decision_score": round(c["decision_score"], 4), "lead_time_risk": c["lead"].risk.value,
            "reliability_score": c["rel"].score,
        } for c in candidates[1:4]]
        action = PurchaseRecommendation(
            supplier_id=rank.supplier_id, product_id=context.entity_id, qty=round(chosen["qty"], 2),
            unit_cost=rank.unit_cost, expected_cost=round(chosen["expected_cost"], 2), eta_days=lead.p90_days,
            supplier_score=rank.score, reliability_score=rel.score, lead_time_risk=lead.risk, risk=risk,
            currency="ZAR", decision_score=round(chosen["decision_score"], 4), alternatives=alternatives,
        )
        guardrails = ["human_approval_required"]
        if rank.moq > reorder.recommended_qty:
            guardrails.append("quantity_raised_to_moq")
        if second_review_required(action.expected_cost, risk):
            guardrails.append("second_review_required")
        rationale = [
            f"R4 selected {rank.supplier_name} after combining the R1 supplier score, R2 reliability score and R3 lead-time risk.",
            f"Quantity {action.qty:g} respects the supplier MOQ and the external Inventory reorder requirement.",
            f"The external demand forecast confidence is {forecast.confidence:.0%}; safety-stock target is {safety.safety_stock:g} units.",
            "The recommendation is advisory and cannot create a purchase order until a manager approves or modifies it.",
        ]
        confidence = min(0.96, 0.50 + 0.25 * rel.confidence + 0.15 * lead.confidence + 0.10 * forecast.confidence)
        return self.result(
            context, "PurchaseRecommendation", action.model_dump(mode="json"), rationale,
            ["I2:ReorderNeed", "I3:SafetyStockTarget", "D4:DemandForecast", "R1:SupplierComparison", "R2:SupplierReliabilityScore", "R3:LeadTimeRisk"],
            confidence, risk, True, guardrails,
        )
