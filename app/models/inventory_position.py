"""
InventoryPosition — the formal output contract of I1 Stock Monitor.

This is the object I2 (Reorder Point Agent) consumes to decide whether
a reorder is needed. I1 produces it; I1 does NOT decide whether to reorder.

Fields intentionally limited to what I1 can observe from the snapshot and
demand forecast (for context only). The reorder decision belongs to I2.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models.alert import StockStatus


@dataclass
class InventoryPosition:
    """
    The current inventory position for a single (product, store) as
    assessed by I1 Stock Monitor.

    Produced by: StockMonitor.get_inventory_positions()
    Consumed by: I2 Reorder Point Agent (not yet implemented)

    What I1 guarantees:
        - available_stock = stock_on_hand - reserved - damaged  (exact formula)
        - stock_status    = I1 classification based on days_of_supply
        - days_of_supply  = monitoring metric; NOT a reorder decision
        - forecast_7d_demand = read from demand_forecasts.json for context;
                               I1 does NOT use it to calculate a reorder point

    What I1 does NOT decide:
        - Whether a reorder is needed (I2)
        - The reorder quantity (I2)
        - The reorder point value (I2)
        - Safety stock (I3)
    """

    # Identity
    product_id: str
    sku: str
    product_name: str
    category: str
    store_id: str
    snapshot_timestamp: datetime

    # Raw stock fields (direct from inventory_snapshots.csv)
    stock_on_hand: float
    reserved: float
    damaged: float
    in_transit: float

    # I1 computed fields
    available_stock: float          # = stock_on_hand - reserved - damaged
    stock_status: StockStatus       # I1 classification
    days_of_supply: Optional[float] # monitoring metric (None if demand rate = 0)
    needs_attention: bool           # True for any non-HEALTHY status

    # Demand forecast context (read-only, for I2 to use — not an I1 decision)
    forecast_7d_demand: float       # expected_qty from demand_forecasts.json
    forecast_confidence: float      # confidence from demand_forecasts.json
    forecast_source: str            # source field — discriminates mock vs real

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "product_name": self.product_name,
            "category": self.category,
            "store_id": self.store_id,
            "snapshot_timestamp": self.snapshot_timestamp.isoformat(),
            # Raw stock
            "stock_on_hand": self.stock_on_hand,
            "reserved": self.reserved,
            "damaged": self.damaged,
            "in_transit": self.in_transit,
            # I1 computed
            "available_stock": self.available_stock,
            "stock_status": self.stock_status.value,
            "days_of_supply": (
                round(self.days_of_supply, 2)
                if self.days_of_supply is not None
                else None
            ),
            "needs_attention": self.needs_attention,
            # Demand context (I2 will consume for reorder calculation)
            "forecast_7d_demand": self.forecast_7d_demand,
            "forecast_confidence": self.forecast_confidence,
            "forecast_source": self.forecast_source,
        }
