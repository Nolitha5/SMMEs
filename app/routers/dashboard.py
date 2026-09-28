"""Dashboard and demand forecast endpoints."""
from typing import Optional
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/", summary="I1 inventory monitoring dashboard KPIs")
def dashboard(request: Request):
    monitor = request.app.state.monitor
    return monitor.get_dashboard()


@router.get("/forecasts", summary="Loaded demand forecasts (Demand → Inventory contract)")
def demand_forecasts(
    request: Request,
    product_id: Optional[str] = Query(None),
):
    """
    Read-only view of the demand_forecasts.json contract.
    I1 reads but does not generate forecasts.
    I2 and I3 will consume these for reorder point and safety stock.
    """
    monitor = request.app.state.monitor
    forecasts = monitor.get_demand_forecasts(product_id=product_id)
    return {
        "source": forecasts[0]["source"] if forecasts else "none",
        "count": len(forecasts),
        "forecasts": forecasts,
    }


@router.get("/suppliers", summary="Supplier list (loaded for I2/I3 future use)")
def suppliers(request: Request):
    monitor = request.app.state.monitor
    return {
        "suppliers": monitor.get_suppliers(),
        "performance": monitor.get_supplier_performance(),
    }
