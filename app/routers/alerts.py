"""Alerts endpoints — I1 Stock Monitor."""
from typing import Optional
from collections import Counter
from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", summary="All active stock alerts")
def get_alerts(
    request: Request,
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    severity: Optional[str] = Query(
        None, description="Minimum severity: CRITICAL | HIGH | MEDIUM | LOW"
    ),
):
    monitor = request.app.state.monitor
    alerts = monitor.generate_alerts(store_id=store_id, severity_filter=severity)
    return {
        "store_id": store_id or "ALL",
        "severity_filter": severity,
        "total": len(alerts),
        "alerts": alerts,
    }


@router.get("/critical", summary="CRITICAL severity alerts only")
def critical_alerts(request: Request):
    monitor = request.app.state.monitor
    alerts = monitor.generate_alerts(severity_filter="CRITICAL")
    return {"total": len(alerts), "alerts": alerts}


@router.get("/summary", summary="Alert counts grouped by severity and status")
def alert_summary(request: Request):
    monitor = request.app.state.monitor
    alerts = monitor.generate_alerts()
    return {
        "total": len(alerts),
        "by_severity": dict(Counter(a["severity"] for a in alerts)),
        "by_stock_status": dict(Counter(a["stock_status"] for a in alerts)),
        "by_alert_type": dict(Counter(a["alert_type"] for a in alerts)),
    }
