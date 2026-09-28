from .products import router as products_router
from .stock import router as stock_router
from .alerts import router as alerts_router
from .reorders import router as reorders_router
from .transactions import router as transactions_router
from .dashboard import router as dashboard_router
from .safety_stock import router as safety_stock_router
from .stock_risk import router as stock_risk_router
from .inventory_exceptions import router as inventory_exceptions_router

__all__ = [
    "products_router",
    "stock_router",
    "alerts_router",
    "reorders_router",
    "transactions_router",
    "dashboard_router",
    "safety_stock_router",
    "stock_risk_router",
    "inventory_exceptions_router",
]
