import pytest

from app.contracts.models import ApprovalDecision
from app.coordination.approval import ApprovalService
from app.coordination.coordinator import ProcurementCoordinator


@pytest.mark.asyncio
async def test_end_to_end_recommend_approve_execute_reconcile_close(repo):
    coordinator = ProcurementCoordinator(repo)
    rec = await coordinator.recommend_purchase("SKU-100", "manager")
    approved = ApprovalService(repo).decide(rec.recommendation_id, ApprovalDecision(decision="APPROVED", reason="Stock risk confirmed"), "manager")
    assert approved["status"] == "APPROVED"
    po = coordinator.execute_purchase_recommendation(rec.recommendation_id, "manager")
    assert po["recommendation_id"] == rec.recommendation_id
    assert repo.get("agent_recommendations", rec.recommendation_id, "recommendation_id")["status"] == "EXECUTED"

    repo.upsert("goods_receipts", {"receipt_id":"GR-E2E","po_id":po["po_id"],"supplier_id":po["supplier_id"],"product_id":po["product_id"],"qty_received":po["qty"],"qty_defective":0,"received_at":po["promised_date"] + "T10:00:00Z"}, "receipt_id")
    repo.upsert("invoices", {"invoice_id":"INV-E2E","invoice_number":"E2E-001","po_id":po["po_id"],"supplier_id":po["supplier_id"],"product_id":po["product_id"],"qty_invoiced":po["qty"],"unit_cost":po["unit_cost"],"tax_amount":0,"currency":"ZAR","invoiced_at":po["promised_date"] + "T12:00:00Z"}, "invoice_id")
    reconciliation = await coordinator.reconcile(po["po_id"], "manager")
    assert reconciliation.action["match_status"] == "MATCH"
    closed = coordinator.close_purchase_order(po["po_id"], reconciliation.recommendation_id, "manager")
    assert closed["purchase_order"]["status"] == "CLOSED"
    assert repo.get("supplier_performance", po["po_id"], "po_id") is not None


def test_execution_is_idempotent_after_approval(repo):
    # Seed a simple approved R4 record directly to isolate idempotency.
    rec = {"recommendation_id":"REC-IDEMP","agent_id":"R4","status":"APPROVED","action":{"supplier_id":"SUP-001","product_id":"SKU-100","qty":100,"unit_cost":18.5,"currency":"ZAR","eta_days":5}}
    repo.upsert("agent_recommendations", rec, "recommendation_id")
    coordinator = ProcurementCoordinator(repo)
    first = coordinator.execute_purchase_recommendation("REC-IDEMP", "manager")
    # Once executed the recommendation is EXECUTED, but retry should return same PO rather than duplicate.
    second = coordinator.execute_purchase_recommendation("REC-IDEMP", "manager")
    assert first["po_id"] == second["po_id"]
    assert len([p for p in repo.list("purchase_orders") if p.get("recommendation_id") == "REC-IDEMP"]) == 1
