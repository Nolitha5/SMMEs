"""
I5 Inventory Exceptions router.

GET /api/inventory-exceptions                — all detected exceptions
GET /api/inventory-exceptions/{product_id}   — exceptions for one product
"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/inventory-exceptions", tags=["I5 Inventory Exceptions"])


@router.get("/", summary="All detected inventory exceptions")
def get_all_inventory_exceptions(request: Request):
    agent = request.app.state.inventory_exception_agent
    exceptions = agent.get_all_exceptions()
    return {
        "total_exceptions": len(exceptions),
        "exceptions": exceptions,
    }


@router.get("/{product_id}", summary="Inventory exceptions for one product")
def get_inventory_exceptions_for_product(product_id: str, request: Request):
    agent = request.app.state.inventory_exception_agent
    result = agent.get_exceptions_for_product(product_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_id.upper()}' not found.",
        )
    return {
        "product_id":        product_id.upper(),
        "active_exceptions": len(result),
        "exceptions":        result,
    }
