"""
I3 Safety Stock Agent — REST endpoints.

Endpoints:
    GET  /api/safety-stock                  — all I3 safety-stock targets
    GET  /api/safety-stock/{product_id}     — I3 target for one product

These endpoints are READ-ONLY. I3 produces targets only.
No inventory is modified here.
All recommendations have requires_approval=False.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/safety-stock", tags=["I3 Safety Stock"])


@router.get("/", summary="All I3 safety-stock targets")
def get_all_safety_stock_targets(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns the I3 safety-stock target for every product that has
    sufficient demand-forecast and supplier data.

    Each result contains:
    - SafetyStockTarget (formula inputs + output)
    - AgentResult recommendation (action, rationale, confidence)

    All recommendations have requires_approval=False.
    I3 never modifies inventory or places orders.
    """
    agent = request.app.state.safety_stock_agent
    monitor = request.app.state.monitor

    # Build product list from I1 monitor so we have category info
    product_list = [
        {"product_id": p.product_id, "category": p.category}
        for p in monitor._products.values()
    ]

    targets = agent.get_all_targets(products=product_list, store_id=store_id)

    total_ss = sum(t["safety_stock"] for t in targets)

    return {
        "agent": "I3_SAFETY_STOCK",
        "formula_version": "I3-v1",
        "store_id": store_id or "ALL",
        "total_products_evaluated": len(targets),
        "total_safety_stock_units": total_ss,
        "service_level": agent._service_level,
        "z_score": agent._z,
        "requires_approval": False,
        "targets": targets,
    }


@router.get("/{product_id}", summary="I3 safety-stock target for one product")
def get_product_safety_stock(
    product_id: str,
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns the I3 safety-stock target for a single product.

    Returns 404 if the product does not exist or has insufficient data.
    """
    agent = request.app.state.safety_stock_agent
    monitor = request.app.state.monitor

    pid = product_id.strip().upper()
    product = monitor._products.get(pid)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Product '{product_id}' not found."
            ),
        )

    result = agent.get_target_for_product(
        product_id=pid,
        category=product.category,
        store_id=store_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No I3 safety-stock target available for product '{product_id}'. "
                "Demand forecast or supplier data is missing."
            ),
        )

    return result
