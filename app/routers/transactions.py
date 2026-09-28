"""Transaction and movement history endpoints."""
from typing import Optional
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("/", summary="Recent sales transactions")
def list_transactions(
    request: Request,
    product_id: Optional[str] = Query(None),
    store_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    monitor = request.app.state.monitor
    txns = monitor.get_transactions(
        product_id=product_id, store_id=store_id, limit=limit
    )
    return {
        "count": len(txns),
        "filters": {"product_id": product_id, "store_id": store_id},
        "transactions": txns,
    }


@router.get("/movements", summary="Inventory movements (receipts, adjustments)")
def list_movements(
    request: Request,
    product_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    monitor = request.app.state.monitor
    movements = monitor.get_movements(product_id=product_id, limit=limit)
    return {"count": len(movements), "movements": movements}
