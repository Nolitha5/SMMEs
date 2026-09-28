from __future__ import annotations

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.contracts.models import (
    AgentContext, ApprovalDecision, DemandForecast, GoodsReceipt, PurchaseOrder,
    ReorderNeed, SafetyStockTarget, Supplier, SupplierInvoice, SupplierPerformance,
    SupplierQuote,
)
from app.contracts.shared import (
    COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_AGENT_RUNS,
    COLLECTION_AGENT_STATE, COLLECTION_APPROVAL_LOG, COLLECTION_OUTCOMES,
    COLLECTION_SYSTEM_EVENTS, PROCUREMENT_OPERATIONAL_COLLECTIONS, SHARED_READ_ONLY_COLLECTIONS,
    InventoryPosition,
)
from app.coordination.approval import ApprovalService
from app.coordination.coordinator import ProcurementCoordinator
from app.core.auth import UserPrincipal, current_user, require_manager
from app.core.config import get_settings
from app.data.bootstrap import bootstrap_sample_data, seed_upstream_contracts
from app.data.factory import get_repository
from app.data.output_repository import OutputRepository
from app.data.repository import Repository
from app.services import events
from app.services.audit_history import build_audit_history
from app.services.imports import import_records, parse_csv_bytes
from app.services.storage import archive_import

router = APIRouter()


def repo_dep() -> Repository:
    return get_repository()


# Operational collections Procurement owns. Imported/upserted as plain records.
IMPORT_MODELS = {
    "suppliers": (Supplier, "supplier_id"),
    "supplier_quotes": (SupplierQuote, "quote_id"),
    "supplier_performance": (SupplierPerformance, "performance_id"),
    "purchase_orders": (PurchaseOrder, "po_id"),
    "goods_receipts": (GoodsReceipt, "receipt_id"),
    "invoices": (SupplierInvoice, "invoice_id"),
}

# Upstream published contracts. A CSV import here does NOT create a Procurement
# collection; it publishes into agent_outputs/agent_state on behalf of the
# owning agent, exactly as that agent would in the shared system.
UPSTREAM_IMPORTS = {
    "demand_forecasts": ("D4", DemandForecast),
    "inventory_positions": ("I1", InventoryPosition),
    "reorder_needs": ("I2", ReorderNeed),
    "safety_stock_targets": ("I3", SafetyStockTarget),
}

UPSERT_MODELS = IMPORT_MODELS

# Everything the read endpoint may expose. Protected exchange/governance
# collections are readable through the backend but never written by a client.
READABLE_COLLECTIONS = (
    PROCUREMENT_OPERATIONAL_COLLECTIONS
    | SHARED_READ_ONLY_COLLECTIONS
    | {
        COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_STATE, COLLECTION_AGENT_RUNS,
        COLLECTION_SYSTEM_EVENTS, COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_APPROVAL_LOG,
        COLLECTION_OUTCOMES,
    }
)


@router.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "service": s.app_name, "version": s.app_version, "scope": "Procurement R1-R5"}


@router.get("/ready")
def ready(repo: Repository = Depends(repo_dep)):
    return {"status": "ready", "repository": get_settings().repository_backend, "suppliers": len(repo.list("suppliers"))}


@router.get("/me")
def me(user: UserPrincipal = Depends(current_user)):
    return {"uid": user.uid, "email": user.email, "role": user.role}


@router.post("/demo/bootstrap")
def demo_bootstrap(user: UserPrincipal = Depends(require_manager), repo: Repository = Depends(repo_dep)):
    """DEV/TEST COMPATIBILITY ONLY — loads sample data for standalone runs."""
    return bootstrap_sample_data(repo)


@router.get("/agents/status")
def agent_status(repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    return ProcurementCoordinator(repo).agent_statuses()


@router.post("/agents/{agent_id}/run")
async def run_agent(agent_id: str, context: AgentContext, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    context.actor_id = user.uid
    return await ProcurementCoordinator(repo).run_agent(agent_id.upper(), context)


@router.post("/procurement/recommend/{product_id}")
async def recommend(product_id: str, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    return await ProcurementCoordinator(repo).recommend_purchase(product_id, user.uid)


@router.post("/procurement/reconcile/{po_id}")
async def reconcile(po_id: str, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    return await ProcurementCoordinator(repo).reconcile(po_id, user.uid)


@router.post("/procurement/close/{po_id}/{reconciliation_id}")
def close_po(po_id: str, reconciliation_id: str, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    return ProcurementCoordinator(repo).close_purchase_order(po_id, reconciliation_id, user.uid)


@router.get("/recommendations")
def recommendations(
    agent_id: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    repo: Repository = Depends(repo_dep),
    _: UserPrincipal = Depends(current_user),
):
    rows = repo.list("agent_recommendations")
    if agent_id:
        rows = [r for r in rows if r.get("agent_id") == agent_id.upper()]
    if status:
        rows = [r for r in rows if r.get("status") == status.upper()]
    if risk:
        rows = [r for r in rows if r.get("risk_level") == risk.upper()]
    return sorted(rows, key=lambda r: r.get("generated_at", ""), reverse=True)


@router.get("/recommendations/{recommendation_id}")
def recommendation(recommendation_id: str, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    row = repo.get("agent_recommendations", recommendation_id, "recommendation_id")
    if not row:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return row


@router.post("/recommendations/{recommendation_id}/decision")
def decide(recommendation_id: str, decision: ApprovalDecision, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    return ApprovalService(repo).decide(recommendation_id, decision, user.uid)


@router.post("/recommendations/{recommendation_id}/execute")
def execute(recommendation_id: str, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    return ProcurementCoordinator(repo).execute_purchase_recommendation(recommendation_id, user.uid)


@router.post("/imports/{collection}")
async def import_csv(collection: str, file: Annotated[UploadFile, File()], repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    if collection not in IMPORT_MODELS and collection not in UPSTREAM_IMPORTS:
        raise HTTPException(status_code=404, detail=f"Unsupported import collection: {collection}")
    raw = await file.read()
    archive = archive_import(raw, file.filename or f"{collection}.csv", user.uid)
    rows = parse_csv_bytes(raw)

    if collection in UPSTREAM_IMPORTS:
        # DEV/TEST COMPATIBILITY ONLY. Procurement is not the producer of these
        # contracts; in the shared system Demand/Inventory publish them and this
        # path is disabled.
        if not get_settings().allow_upstream_fixtures:
            raise HTTPException(
                status_code=403,
                detail=f"Upstream contract import '{collection}' is disabled in shared mode; "
                       "this contract is published by its owning domain, not by Procurement.",
            )
        agent_id, model = UPSTREAM_IMPORTS[collection]
        seeded = seed_upstream_contracts(repo, agent_id, rows, model)
        response = {
            "collection": f"agent_state:{agent_id}",
            "imported": seeded["published"],
            "rejected": seeded["rejected"],
            "duplicate_ids": seeded["duplicate_ids"],
            "errors": seeded["errors"],
        }
    else:
        model, key = IMPORT_MODELS[collection]
        result = import_records(repo, collection, rows, model, key)
        response = result.model_dump(mode="json")
        if collection == "goods_receipts":
            for row in rows:
                if row.get("receipt_id") and row.get("po_id"):
                    events.publish_event(
                        repo, events.EVENT_GOODS_RECEIPT_RECORDED, "purchase_order", str(row["po_id"]), user.uid,
                        {"receipt_id": row["receipt_id"]}, idempotency_key=str(row["receipt_id"]),
                    )
        elif collection == "invoices":
            for row in rows:
                if row.get("invoice_id") and row.get("po_id"):
                    events.publish_event(
                        repo, events.EVENT_INVOICE_RECEIVED, "purchase_order", str(row["po_id"]), user.uid,
                        {"invoice_id": row["invoice_id"]}, idempotency_key=str(row["invoice_id"]),
                    )

    # Import provenance is the returned checksum/archive metadata (and the
    # Storage archive when configured); an import is bookkeeping, not a trigger.
    response["source_archive"] = archive
    return response


@router.get("/data/{collection}")
def list_data(collection: str, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    if collection not in READABLE_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Unknown collection")
    return repo.list(collection)


@router.put("/data/{collection}")
def upsert_data(collection: str, payload: dict, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(require_manager)):
    """Upsert one operational record. Exchange and governance collections are never writable here."""
    if collection not in UPSERT_MODELS:
        raise HTTPException(status_code=404, detail="Unsupported collection")
    model, key = UPSERT_MODELS[collection]
    parsed = model.model_validate(payload).model_dump(mode="json")
    repo.upsert(collection, parsed, key)
    if collection == "goods_receipts":
        events.publish_event(
            repo, events.EVENT_GOODS_RECEIPT_RECORDED, "purchase_order", str(parsed["po_id"]), user.uid,
            {"receipt_id": parsed[key]}, idempotency_key=str(parsed[key]),
        )
    elif collection == "invoices":
        events.publish_event(
            repo, events.EVENT_INVOICE_RECEIVED, "purchase_order", str(parsed["po_id"]), user.uid,
            {"invoice_id": parsed[key]}, idempotency_key=str(parsed[key]),
        )
    return parsed


@router.get("/outputs/{output_type}/{entity_id}")
def latest_output(output_type: str, entity_id: str, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    """Latest valid shared-state projection for a contract. 404 when absent or stale."""
    env = OutputRepository(repo).get_latest_output(output_type, entity_id)
    if not env:
        raise HTTPException(status_code=404, detail="No valid output in agent_state for this contract")
    return env.model_dump(mode="json")


@router.get("/outputs/{output_type}/{entity_id}/history")
def output_history(output_type: str, entity_id: str, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    return OutputRepository(repo).history(output_type, entity_id)


@router.get("/runs/{run_id}")
def agent_run(run_id: str, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    row = repo.get(COLLECTION_AGENT_RUNS, run_id, "run_id")
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return row


@router.get("/suppliers/{supplier_id}/scorecard")
async def supplier_scorecard(supplier_id: str, repo: Repository = Depends(repo_dep), user: UserPrincipal = Depends(current_user)):
    coordinator = ProcurementCoordinator(repo)
    ctx = AgentContext(entity_type="supplier", entity_id=supplier_id, payload={"supplier_id": supplier_id}, actor_id=user.uid)
    r2 = await coordinator.run_agent("R2", ctx)
    r3_ctx = AgentContext(entity_type="supplier", entity_id=supplier_id, payload={"supplier_id": supplier_id}, prior_outputs={"R2": r2.action}, actor_id=user.uid)
    r3 = await coordinator.run_agent("R3", r3_ctx)
    supplier = repo.get("suppliers", supplier_id, "supplier_id")
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"supplier": supplier, "reliability": r2.action, "lead_time": r3.action}


@router.get("/dashboard")
def dashboard(repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    recs = repo.list("agent_recommendations")
    pos = repo.list("purchase_orders")
    suppliers = repo.list("suppliers")
    pending = [r for r in recs if r.get("status") == "READY_FOR_REVIEW"]
    exceptions = [r for r in recs if r.get("agent_id") == "R5" and (r.get("action") or {}).get("exception_types")]
    open_pos = [p for p in pos if p.get("status") not in {"CLOSED", "CANCELLED"}]
    spend = sum(float(p.get("qty", 0)) * float(p.get("unit_cost", 0)) for p in pos)
    return {
        "active_suppliers": sum(1 for s in suppliers if s.get("status") == "ACTIVE"),
        "pending_approvals": len(pending),
        "open_purchase_orders": len(open_pos),
        "procurement_exceptions": len(exceptions),
        "purchase_order_value": round(spend, 2),
        "recommendations_by_agent": dict(Counter(r.get("agent_id") for r in recs)),
        "agent_status": ProcurementCoordinator(repo).agent_statuses(),
    }


@router.get("/audit")
def audit(entity_id: str | None = None, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    """Audit history composed on read from the canonical shared collections.

    There is no audit collection. `system_events` carries triggers only; the
    trail below merges agent_runs, agent_outputs, agent_recommendations,
    approval_log, system_events and outcomes, newest first.
    """
    return build_audit_history(repo, entity_id=entity_id)


@router.get("/events")
def system_events(event_type: str | None = None, repo: Repository = Depends(repo_dep), _: UserPrincipal = Depends(current_user)):
    """The raw shared trigger stream, for consumers that route on event_type."""
    rows = repo.list(COLLECTION_SYSTEM_EVENTS)
    if event_type:
        rows = [r for r in rows if r.get("event_type") == event_type]
    return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)
