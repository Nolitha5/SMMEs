from __future__ import annotations

from collections import Counter

from app.agents.base import BaseProcurementAgent
from app.contracts.models import AgentContext, ProcurementException, PurchaseOrder, RiskLevel
from app.services.analytics import parse_datetime


class DeliveryInvoiceReconciliationAgent(BaseProcurementAgent):
    agent_id = "R5"
    name = "Delivery & Invoice Reconciliation"
    version = "1.0.0-r5"

    async def run(self, context: AgentContext):
        po_id = str(context.payload.get("po_id") or context.entity_id)
        po_row = self.repo.get("purchase_orders", po_id, "po_id")
        receipts = [r for r in self.repo.list("goods_receipts") if str(r.get("po_id")) == po_id]
        invoices = [i for i in self.repo.list("invoices") if str(i.get("po_id")) == po_id]
        if not po_row or not receipts or not invoices:
            missing = []
            if not po_row: missing.append("purchase_order")
            if not receipts: missing.append("goods_receipt")
            if not invoices: missing.append("supplier_invoice")
            action = ProcurementException(
                supplier_id=str((po_row or {}).get("supplier_id", "UNKNOWN")), po_id=po_id,
                exception_types=["INSUFFICIENT_EVIDENCE"], details={"missing": missing},
                match_status="INSUFFICIENT_EVIDENCE", financial_variance=0, severity=RiskLevel.HIGH,
            )
            return self.result(
                context, "ProcurementException", action.model_dump(mode="json"),
                [f"Three-way reconciliation cannot be completed because {', '.join(missing)} data is missing."],
                ["purchase_orders", "goods_receipts", "invoices"], 0.0, RiskLevel.HIGH, True,
                ["insufficient_evidence"],
            )

        po = PurchaseOrder.model_validate(po_row)
        qty_tolerance = float(context.payload.get("qty_tolerance", 0))
        cost_tolerance_pct = float(context.payload.get("cost_tolerance_pct", 0.01))
        total_received = sum(float(r.get("qty_received", 0)) for r in receipts)
        total_defective = sum(float(r.get("qty_defective", 0)) for r in receipts)
        total_invoiced_qty = sum(float(i.get("qty_invoiced", 0)) for i in invoices)
        invoice_subtotal = sum(float(i.get("qty_invoiced", 0)) * float(i.get("unit_cost", 0)) for i in invoices)
        expected_subtotal = po.qty * po.unit_cost
        financial_variance = invoice_subtotal - expected_subtotal
        exception_types, details = [], {}

        if total_received < po.qty - qty_tolerance:
            exception_types.append("UNDER_DELIVERY")
            details["receipt_quantity"] = {"ordered": po.qty, "received": total_received}
        elif total_received > po.qty + qty_tolerance:
            exception_types.append("OVER_DELIVERY")
            details["receipt_quantity"] = {"ordered": po.qty, "received": total_received}
        if abs(total_invoiced_qty - total_received) > qty_tolerance:
            exception_types.append("INVOICE_RECEIPT_QTY_MISMATCH")
            details["invoice_quantity"] = {"received": total_received, "invoiced": total_invoiced_qty}
        allowed_cost_variance = max(expected_subtotal * cost_tolerance_pct, 0.01)
        if abs(financial_variance) > allowed_cost_variance:
            exception_types.append("PRICE_VARIANCE")
            details["financial"] = {"expected_subtotal": round(expected_subtotal, 2), "invoice_subtotal": round(invoice_subtotal, 2), "variance": round(financial_variance, 2)}
        if total_defective > 0:
            exception_types.append("DEFECTIVE_GOODS")
            details["defects"] = {"qty_defective": total_defective}
        latest_receipt = max(parse_datetime(r["received_at"]) for r in receipts)
        if latest_receipt.date() > po.promised_date:
            exception_types.append("LATE_DELIVERY")
            details["delivery"] = {"promised_date": po.promised_date.isoformat(), "actual_date": latest_receipt.date().isoformat(), "days_late": (latest_receipt.date() - po.promised_date).days}
        numbers = [str(i.get("invoice_number", "")) for i in self.repo.list("invoices") if i.get("invoice_number")]
        dup_numbers = [n for n, c in Counter(numbers).items() if c > 1 and any(str(i.get("invoice_number")) == n for i in invoices)]
        if dup_numbers:
            exception_types.append("DUPLICATE_INVOICE_NUMBER")
            details["duplicate_invoice_numbers"] = dup_numbers

        if not exception_types:
            status, severity = "MATCH", RiskLevel.LOW
        else:
            high_impact = {"PRICE_VARIANCE", "DUPLICATE_INVOICE_NUMBER", "OVER_DELIVERY"}
            severity = RiskLevel.HIGH if high_impact.intersection(exception_types) else RiskLevel.MEDIUM
            status = "MISMATCH" if severity == RiskLevel.HIGH else "PARTIAL_MATCH"
        action = ProcurementException(
            supplier_id=po.supplier_id, po_id=po_id, exception_types=exception_types, details=details,
            match_status=status, financial_variance=round(financial_variance, 2), severity=severity,
        )
        rationale = [
            "R5 completed a deterministic three-way match across the approved purchase order, goods receipts and supplier invoice(s).",
            f"Result: {status}; exceptions detected: {', '.join(exception_types) if exception_types else 'none'}.",
        ]
        return self.result(
            context, "ProcurementException", action.model_dump(mode="json"), rationale,
            [f"purchase_orders:{po_id}", "goods_receipts", "invoices"],
            0.98, severity, bool(exception_types), ["three_way_match"],
        )
