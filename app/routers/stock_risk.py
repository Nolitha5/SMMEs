"""
I4 Stock Risk router.

GET /api/stock-risk             — all products with active risk alerts
GET /api/stock-risk/{product_id} — risk alerts for one product
"""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/stock-risk", tags=["I4 Stock Risk"])


@router.get("/", summary="All products with active stock risk")
def get_all_stock_risks(request: Request):
    agent = request.app.state.stock_risk_agent
    alerts = agent.get_all_alerts()
    return {
        "total_alerts": len(alerts),
        "observation_days": agent._observation_days,
        "alerts": alerts,
    }


@router.get("/{product_id}", summary="Stock risk for one product")
def get_stock_risk_for_product(product_id: str, request: Request):
    agent = request.app.state.stock_risk_agent
    result = agent.get_alerts_for_product(product_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")
    return {
        "product_id": product_id.upper(),
        "active_risks": len(result),
        "alerts": result,
    }
