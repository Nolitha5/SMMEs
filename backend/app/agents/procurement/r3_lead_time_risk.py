from __future__ import annotations

from statistics import mean, median

from app.agents.base import BaseProcurementAgent
from app.contracts.models import AgentContext, LeadTimeRisk, RiskLevel
from app.services.analytics import parse_date, percentile, robust_std


class LeadTimeRiskAgent(BaseProcurementAgent):
    agent_id = "R3"
    name = "Lead-Time Risk"
    version = "1.0.0-r3"

    async def run(self, context: AgentContext):
        supplier_id = str(context.payload.get("supplier_id") or context.entity_id)
        rows = self.rows("supplier_performance", supplier_id=supplier_id)
        lead_days, delayed = [], []
        for row in rows:
            try:
                order_date = parse_date(row["order_date"])
                actual_date = parse_date(row["actual_date"])
                promised_date = parse_date(row["promised_date"])
                lead_days.append(max((actual_date - order_date).days, 1))
                delayed.append(1 if actual_date > promised_date else 0)
            except Exception:
                continue

        fallback = False
        if not lead_days:
            quotes = [q for q in self.repo.list("supplier_quotes") if str(q.get("supplier_id")) == supplier_id]
            quoted = min([float(q.get("quoted_lead_time_days", 7)) for q in quotes], default=7.0)
            lead_days = [quoted]
            delayed = [0]
            fallback = True

        med = float(median(lead_days))
        expected = float(mean(lead_days))
        p90 = percentile(lead_days, 0.90)
        variability = robust_std(lead_days)
        delay_rate = sum(delayed) / len(delayed) if delayed else 0.0
        if p90 >= 15 or delay_rate >= 0.45 or (med and p90 / med >= 1.8):
            risk = RiskLevel.HIGH
        elif p90 >= 10 or delay_rate >= 0.20 or variability >= 3:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.LOW
        # The blueprint publishes R2 reliability to R3 as policy context.
        # R3 never replaces its lead-time statistics with R2; it only escalates
        # the risk band when broader supplier reliability is materially poor.
        r2 = context.prior_outputs.get("R2") or {}
        reliability_score = r2.get("score") if isinstance(r2, dict) else None
        if reliability_score is not None:
            reliability_score = float(reliability_score)
            if reliability_score < 0.55:
                risk = RiskLevel.HIGH
            elif reliability_score < 0.75 and risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
        confidence = 0.25 if fallback else min(0.96, 0.30 + len(lead_days) / 10)
        action = LeadTimeRisk(
            supplier_id=supplier_id, median_days=round(med, 2), expected_days=round(expected, 2),
            p90_days=round(p90, 2), variability_days=round(variability, 2), delay_rate=round(delay_rate, 4),
            risk=risk, sample_size=0 if fallback else len(lead_days), confidence=round(confidence, 4),
        )
        rationale = ["Estimated realistic lead time using historical median, P90 tail time, variability and delay frequency."]
        if reliability_score is not None:
            rationale.append(f"R2 reliability ({reliability_score:.1%}) was used as risk-escalation context, not as a substitute for lead-time evidence.")
        guardrails = []
        if fallback:
            rationale.append("No usable delivery history was available; quoted lead time was used as a low-confidence fallback.")
            guardrails.append("quoted_lead_time_fallback")
        return self.result(
            context, "LeadTimeRisk", action.model_dump(mode="json"), rationale,
            ["supplier_performance", "supplier_quotes"], confidence, risk, False, guardrails,
        )
