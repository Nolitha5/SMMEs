from __future__ import annotations

from datetime import date

from app.agents.base import BaseProcurementAgent
from app.contracts.models import AgentContext, RiskLevel, SupplierReliabilityScore
from app.services.analytics import clamp, parse_date, recency_weight, weighted_mean


class SupplierReliabilityAgent(BaseProcurementAgent):
    agent_id = "R2"
    name = "Supplier Reliability"
    version = "1.0.0-r2"

    async def run(self, context: AgentContext):
        supplier_id = str(context.payload.get("supplier_id") or context.entity_id)
        rows = self.rows("supplier_performance", supplier_id=supplier_id)
        if not rows:
            action = SupplierReliabilityScore(
                supplier_id=supplier_id, score=0.5, on_time_rate=0.5, fill_rate=0.5,
                defect_rate=0.0, invoice_accuracy=0.5, sample_size=0, confidence=0.2,
            )
            return self.result(
                context, "SupplierReliabilityScore", action.model_dump(mode="json"),
                ["No closed delivery history exists; a neutral prior is reported instead of false precision."],
                ["supplier_performance"], 0.2, RiskLevel.MEDIUM, False, ["limited_history"],
            )

        today = date.today()
        on_time_pairs, fill_pairs, defect_pairs, invoice_pairs = [], [], [], []
        for row in rows:
            actual = parse_date(row["actual_date"])
            promised = parse_date(row["promised_date"])
            weight = recency_weight((today - actual).days)
            ordered = max(float(row.get("ordered_qty", 0)), 1e-9)
            received = max(float(row.get("received_qty", 0)), 0)
            defects = max(float(row.get("defect_qty", 0)), 0)
            fill = clamp(received / ordered)
            defect_rate = clamp(defects / received) if received else 0.0
            invoice_accuracy = 1.0 - clamp(abs(float(row.get("invoice_variance_pct", 0))) / 0.10)
            on_time_pairs.append((1.0 if actual <= promised else 0.0, weight))
            fill_pairs.append((fill, weight))
            defect_pairs.append((defect_rate, weight))
            invoice_pairs.append((invoice_accuracy, weight))

        on_time = weighted_mean(on_time_pairs, 0.5)
        fill_rate = weighted_mean(fill_pairs, 0.5)
        defect_rate = weighted_mean(defect_pairs, 0.0)
        invoice_accuracy = weighted_mean(invoice_pairs, 0.5)
        score = clamp(0.40 * on_time + 0.35 * fill_rate + 0.15 * (1 - defect_rate) + 0.10 * invoice_accuracy)
        confidence = min(0.98, 0.25 + len(rows) / 12)
        risk = RiskLevel.HIGH if score < 0.55 else RiskLevel.MEDIUM if score < 0.75 else RiskLevel.LOW
        action = SupplierReliabilityScore(
            supplier_id=supplier_id, score=round(score, 4), on_time_rate=round(on_time, 4),
            fill_rate=round(fill_rate, 4), defect_rate=round(defect_rate, 4), invoice_accuracy=round(invoice_accuracy, 4),
            sample_size=len(rows), confidence=round(confidence, 4),
        )
        return self.result(
            context, "SupplierReliabilityScore", action.model_dump(mode="json"),
            ["Calculated a recency-weighted supplier score from on-time delivery, fill rate, defects and invoice accuracy.",
             f"The score is based on {len(rows)} closed delivery record(s)."],
            ["supplier_performance"], confidence, risk, False,
        )
