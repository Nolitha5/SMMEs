"""Stock levels endpoints — uses store_id from shared dataset."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/stock", tags=["Stock Levels"])


@router.get("/", summary="Latest stock summary for all active products")
def stock_summary(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID (e.g. STORE-001)"),
):
    monitor = request.app.state.monitor
    summary = monitor.get_stock_summary(store_id=store_id)
    return {
        "store_id": store_id or "ALL",
        "count": len(summary),
        "items": summary,
    }


@router.get("/stores", summary="List known store IDs")
def list_stores(request: Request):
    monitor = request.app.state.monitor
    return {"stores": monitor._stores}


@router.get("/{product_id}", summary="All historical snapshots for one product")
def stock_for_product(product_id: str, request: Request):
    monitor = request.app.state.monitor
    product = monitor.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    levels = monitor.get_stock_for_product(product_id)
    return {
        "product": product,
        "snapshot_count": len(levels),
        "snapshots": levels,
    }


@router.post("/reload", summary="Reload all data files from disk")
def reload_data(request: Request):
    monitor = request.app.state.monitor
    monitor.reload()
    return {"message": "Data reloaded from disk", "status": "ok"}
