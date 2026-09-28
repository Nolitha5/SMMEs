"""
I2 Reorder Point Agent — REST endpoints.

Endpoints:
    GET  /reorders               — all I2 reorder decisions (all products)
    GET  /reorders/urgent        — only products where reorder_needed = True
    GET  /reorders/insufficient  — products with missing forecast or supplier data
    GET  /reorders/{product_id}  — I2 decision for one product

These endpoints are READ-ONLY. I2 produces recommendations only.
No purchase is placed or inventory modified here.
All recommendations have requires_approval = True.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/reorders", tags=["I2 Reorder Point"])


@router.get("/", summary="All I2 reorder point decisions")
def get_reorder_decisions(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns the I2 reorder-point evaluation for every active product.

    Each result contains:
    - ReorderNeed evidence (inputs + calculated reorder point + decision)
    - AgentResult recommendation (action, rationale, confidence, approval flag)

    All recommendations have requires_approval=True. I2 never executes purchases.
    """
    agent = request.app.state.reorder_agent
    decisions = agent.get_reorder_decisions(store_id=store_id)

    reorder_needed_count = sum(1 for d in decisions if d["reorder_needed"])
    total_suggested_units = sum(
        d["suggested_reorder_qty"] for d in decisions if d["reorder_needed"]
    )

    return {
        "agent": "I2_REORDER_POINT",
        "rule_version": "I2-v1.0-basic-rop",
        "store_id": store_id or "ALL",
        "total_products_evaluated": len(decisions),
        "reorder_needed_count": reorder_needed_count,
        "no_reorder_count": len(decisions) - reorder_needed_count,
        "total_suggested_units": round(total_suggested_units, 0),
        "safety_stock_note": "safety_stock=0 (I3 placeholder — I3 not yet implemented)",
        "requires_approval": True,
        "decisions": decisions,
    }


@router.get("/urgent", summary="Products where reorder is needed (urgent only)")
def get_urgent_reorders(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns only products where reorder_needed = True, sorted by
    inventory_position ascending (most depleted first = highest urgency).

    All recommendations have requires_approval=True.
    """
    agent = request.app.state.reorder_agent
    urgent = agent.get_urgent_reorders(store_id=store_id)

    return {
        "agent": "I2_REORDER_POINT",
        "store_id": store_id or "ALL",
        "urgent_count": len(urgent),
        "requires_approval": True,
        "urgent_reorders": urgent,
    }


@router.get("/insufficient", summary="Products with insufficient data for I2 evaluation")
def get_insufficient_data(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns products for which I2 cannot produce a reorder decision because
    demand forecast or supplier lead time data is missing.

    Safe-failure behaviour: I2 never invents values for missing data.
    These products are flagged so the data gap can be resolved.
    """
    agent = request.app.state.reorder_agent
    missing = agent.get_insufficient_data_products(store_id=store_id)

    return {
        "agent": "I2_REORDER_POINT",
        "store_id": store_id or "ALL",
        "count": len(missing),
        "insufficient_data_products": missing,
    }


@router.get("/{product_id}", summary="I2 reorder decision for one product")
def get_product_reorder(
    product_id: str,
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
):
    """
    Returns the I2 reorder-point decision for a single product.

    Returns 404 if the product is not found or has insufficient data.
    """
    agent = request.app.state.reorder_agent
    decision = agent.get_decision_for_product(
        product_id=product_id.upper(),
        store_id=store_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No I2 decision available for product '{product_id}'. "
                "Either the product does not exist or demand forecast / "
                "supplier data is missing."
            ),
        )

    return decision
