from __future__ import annotations

from datetime import datetime, timezone

from app.agents.base import BaseProcurementAgent
from app.contracts.models import (
    AgentContext, RiskLevel, Supplier, SupplierComparison, SupplierQuote, SupplierRank,
)
from app.services.analytics import normalized_high_is_good, normalized_low_is_good, parse_datetime
from app.services.data_quality import screen_records


class SupplierComparatorAgent(BaseProcurementAgent):
    agent_id = "R1"
    name = "Supplier Comparator"
    version = "1.0.0-r1"

    async def run(self, context: AgentContext):
        product_id = context.entity_id
        requested_qty = max(float(context.payload.get("requested_qty", 1) or 1), 1.0)
        now = datetime.now(timezone.utc)
        # The store enforces no schema, so screen every record against its
        # contract before use. One malformed document must not fail the
        # comparison for every other supplier.
        supplier_rows, excluded_suppliers = screen_records(self.repo.list("suppliers"), Supplier, "supplier_id")
        suppliers = {s["supplier_id"]: s for s in supplier_rows if s.get("status", "ACTIVE") == "ACTIVE"}

        quote_rows, excluded_quotes = screen_records(
            self.rows("supplier_quotes", product_id=product_id), SupplierQuote, "quote_id"
        )
        quotes = []
        stale_count = 0
        for q in quote_rows:
            if q.get("supplier_id") not in suppliers:
                continue
            try:
                if q.get("valid_until") and parse_datetime(q["valid_until"]) < now:
                    stale_count += 1
                    continue
            except Exception:
                stale_count += 1
                continue
            quotes.append(q)

        exclusion_notes = []
        exclusion_guardrails = []
        if excluded_suppliers:
            exclusion_guardrails.append(f"malformed_suppliers_excluded:{len(excluded_suppliers)}")
            exclusion_notes.append(
                f"{len(excluded_suppliers)} supplier record(s) failed schema validation and were excluded: "
                + "; ".join(f"{e['key']} ({e['reason']})" for e in excluded_suppliers[:5])
            )
        if excluded_quotes:
            exclusion_guardrails.append(f"malformed_quotes_excluded:{len(excluded_quotes)}")
            exclusion_notes.append(
                f"{len(excluded_quotes)} supplier quote(s) failed schema validation and were excluded: "
                + "; ".join(f"{e['key']} ({e['reason']})" for e in excluded_quotes[:5])
            )

        if not quotes:
            reason = "No active, non-expired supplier quote is available for this product."
            if excluded_suppliers or excluded_quotes:
                reason = (
                    "No usable supplier quote remains for this product after excluding "
                    "records that failed schema validation."
                )
            return self.result(
                context,
                "SupplierComparison",
                SupplierComparison(product_id=product_id, requested_qty=requested_qty, ranked_suppliers=[]).model_dump(mode="json"),
                [reason, *exclusion_notes],
                ["suppliers", "supplier_quotes"],
                0.0,
                RiskLevel.HIGH,
                True,
                ["insufficient_evidence", f"expired_quotes:{stale_count}", *exclusion_guardrails],
            )

        costs = [float(q["unit_cost"]) for q in quotes]
        moqs = [float(q.get("moq", 1)) for q in quotes]
        leads = [float(q.get("quoted_lead_time_days", 7)) for q in quotes]
        terms = [int(q.get("payment_terms_days") or suppliers[q["supplier_id"]].get("payment_terms_days", 30)) for q in quotes]
        ranked_raw = []
        for q in quotes:
            supplier = suppliers[q["supplier_id"]]
            payment_terms = int(q.get("payment_terms_days") or supplier.get("payment_terms_days", 30))
            cost_score = normalized_low_is_good(float(q["unit_cost"]), min(costs), max(costs))
            lead_score = normalized_low_is_good(float(q.get("quoted_lead_time_days", 7)), min(leads), max(leads))
            terms_score = normalized_high_is_good(payment_terms, min(terms), max(terms))
            moq = float(q.get("moq", 1))
            if moq <= requested_qty:
                moq_score = 1.0
            else:
                overbuy_ratio = (moq - requested_qty) / requested_qty
                moq_score = max(0.0, 1.0 - overbuy_ratio)
            availability = q.get("available_qty")
            coverage_score = 1.0 if availability in (None, "") or float(availability) >= max(moq, requested_qty) else max(float(availability) / max(moq, requested_qty), 0.0)
            score = 0.40 * cost_score + 0.20 * moq_score + 0.20 * lead_score + 0.10 * terms_score + 0.10 * coverage_score
            warnings = []
            if moq > requested_qty:
                warnings.append("MOQ exceeds requested quantity")
            if availability not in (None, "") and float(availability) < max(moq, requested_qty):
                warnings.append("Quoted available quantity may not cover the order")
            ranked_raw.append((score, q, supplier, payment_terms, warnings, {
                "cost": round(cost_score, 4), "moq_fit": round(moq_score, 4), "lead_time": round(lead_score, 4),
                "payment_terms": round(terms_score, 4), "coverage": round(coverage_score, 4),
            }))

        ranked_raw.sort(key=lambda x: (x[0], -float(x[1]["unit_cost"])), reverse=True)
        ranks = []
        for idx, (score, q, supplier, payment_terms, warnings, breakdown) in enumerate(ranked_raw, start=1):
            ranks.append(SupplierRank(
                supplier_id=q["supplier_id"], supplier_name=supplier["name"], score=round(score, 4), rank=idx,
                unit_cost=float(q["unit_cost"]), moq=float(q.get("moq", 1)),
                quoted_lead_time_days=float(q.get("quoted_lead_time_days", 7)), payment_terms_days=payment_terms,
                score_breakdown=breakdown, warnings=warnings,
            ))
        comparison = SupplierComparison(product_id=product_id, requested_qty=requested_qty, ranked_suppliers=ranks)
        confidence = min(0.98, 0.65 + 0.06 * len(ranks))
        guardrails = [f"expired_quotes_ignored:{stale_count}"] if stale_count else []
        return self.result(
            context, "SupplierComparison", comparison.model_dump(mode="json"),
            ["Ranked active suppliers using quoted cost, MOQ fit, quoted lead time, payment terms and product coverage.",
             "Expired or inactive supplier offers were excluded before scoring.",
             *exclusion_notes],
            ["suppliers", "supplier_quotes"], confidence, RiskLevel.LOW, False,
            [*guardrails, *exclusion_guardrails],
        )
