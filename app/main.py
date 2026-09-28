"""
Inventory Management Agent — FastAPI Application Entry Point
I1 Stock Monitor + I2 Reorder Point Agent + I3 Safety Stock +
I4 Expiry & Slow-Stock + I5 Inventory Exception
(Offline, no external APIs or LLM)
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import (
    alerts_router,
    dashboard_router,
    inventory_exceptions_router,
    products_router,
    reorders_router,
    safety_stock_router,
    stock_risk_router,
    stock_router,
    transactions_router,
)
from app.services.stock_monitor import StockMonitor
from app.services.reorder_point import ReorderPointAgent
from app.services.safety_stock import SafetyStockAgent
from app.services.stock_risk import StockRiskAgent
from app.services.inventory_exception import InventoryExceptionAgent

# ------------------------------------------------------------------
# Resolve data directory relative to this file
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent  # project root
DATA_DIR = BASE_DIR / "data"

# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------
app = FastAPI(
    title="Inventory Management Agent — I1 + I2 + I3 + I4 + I5",
    description=(
        "Offline inventory monitoring, reorder point, safety-stock, expiry/slow-stock, "
        "and inventory exception system. "
        "I1 Stock Monitor: stock health, alerts, inventory positions. "
        "I2 Reorder Point Agent: deterministic reorder-point decisions. "
        "I3 Safety Stock Agent: demand-uncertainty and supplier-reliability safety stock. "
        "I4 Expiry & Slow-Stock Agent: expiry risk, slow stock, dead stock, excess stock. "
        "I5 Inventory Exception Agent: negative stock, reconciliation mismatches, "
        "large adjustments, duplicate/suspicious movements. "
        "No internet connection, database, or LLM required."
    ),
    version="5.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Shared state — I1 + I2 + I3 + I4 + I5
# ------------------------------------------------------------------
@app.on_event("startup")
def startup():
    app.state.monitor                   = StockMonitor(data_dir=DATA_DIR)
    app.state.reorder_agent             = ReorderPointAgent(data_dir=DATA_DIR)
    app.state.safety_stock_agent        = SafetyStockAgent(data_dir=DATA_DIR)
    app.state.stock_risk_agent          = StockRiskAgent(data_dir=DATA_DIR)
    app.state.inventory_exception_agent = InventoryExceptionAgent(data_dir=DATA_DIR)
    print(f"[I1 StockMonitor]             Data loaded from: {DATA_DIR}")
    print(f"[I1 StockMonitor]             Products: {len(app.state.monitor._products)}")
    print(f"[I2 ReorderPointAgent]        Suppliers: {len(app.state.reorder_agent._suppliers)}")
    print(f"[I3 SafetyStockAgent]         Forecasts: {len(app.state.safety_stock_agent._forecasts)}")
    print(f"[I4 StockRiskAgent]           Products: {len(app.state.stock_risk_agent._products)}")
    print(f"[I5 InventoryExceptionAgent]  Products: {len(app.state.inventory_exception_agent._products)}")


# ------------------------------------------------------------------
# Root health-check
# ------------------------------------------------------------------
@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Inventory Management Agent",
        "modules": [
            "I1 Stock Monitor",
            "I2 Reorder Point Agent",
            "I3 Safety Stock Agent",
            "I4 Expiry & Slow-Stock Agent",
            "I5 Inventory Exception Agent",
        ],
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    monitor = app.state.monitor
    return {
        "status": "healthy",
        "products_loaded": len(monitor._products),
        "stock_records": len(monitor._snapshots),
        "data_loaded_at": monitor._loaded_at.isoformat(),
    }


# ------------------------------------------------------------------
# Static files  (served at /static/…)
# ------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ------------------------------------------------------------------
# UI Dashboard route
# ------------------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse, tags=["UI"])
def ui_dashboard():
    """Serve the browser-based inventory management UI."""
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------
app.include_router(dashboard_router)
app.include_router(products_router)
app.include_router(stock_router)
app.include_router(alerts_router)
app.include_router(reorders_router)
app.include_router(safety_stock_router)
app.include_router(stock_risk_router)
app.include_router(inventory_exceptions_router)
app.include_router(transactions_router)
