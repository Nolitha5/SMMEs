"""
ReorderNeed — I2 Reorder Point Agent output contract.

This is the evidence object produced by I2 for each (product, store) pair.
It captures every value used in the reorder-point calculation so the
decision is fully auditable and explainable.

Produced by: ReorderPointAgent.evaluate()
Consumed by: I2 router, AgentResult, future I3 (safety stock integration)

What ReorderNeed contains:
    - Inputs from I1 (InventoryPosition): available_stock, in_transit
    - Inputs from demand forecast: average_daily_demand, forecast_confidence
    - Supplier inputs: supplier_id, lead_time_days
    - I3 placeholder: safety_stock (= 0 until I3 is implemented)
    - I2 computed: reorder_point, inventory_position, reorder_needed,
                   suggested_reorder_qty, reason

Formula (deterministic):
    reorder_point     = average_daily_demand × lead_time_days + safety_stock
    inventory_position = available_stock + in_transit
    reorder_needed    = inventory_position <= reorder_point
    suggested_reorder_qty = max(0, reorder_point - inventory_position)
                             (if reorder_needed, else 0)

Safety stock:
    safety_stock = 0 as a temporary baseline until I3 (Safety Stock Agent)
    provides a formal safety-stock target. The field is exposed in full so
    I3 can supply a non-zero value later without changing this contract.

I2 must NOT:
    - Duplicate I1 stock calculations
    - Execute purchases or modify inventory
    - Generate demand forecasts
    - Calculate safety stock (I3's responsibility)
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ReorderNeed:
    """
    I2 Reorder Point Agent decision for a single (product, store) pair.
    """

    # --- Identity ---
    product_id: str
    sku: str
    product_name: str
    category: str
    store_id: str

    # --- Inputs from I1 InventoryPosition ---
    available_stock: float       # stock_on_hand - reserved - damaged  (from I1)
    in_transit: float            # units already on order / in transit (from I1)

    # --- I2 computed position ---
    inventory_position: float    # available_stock + in_transit

    # --- Demand forecast inputs (from demand_forecasts.json) ---
    average_daily_demand: float  # expected_qty / horizon
    demand_forecast: float       # expected_qty (7-day total)
    forecast_horizon: int        # forecast horizon in days (typically 7)
    forecast_confidence: float   # 0.0–1.0

    # --- Supplier inputs (from suppliers.csv, category-to-supplier lookup) ---
    supplier_id: str             # matched supplier
    supplier_name: str
    lead_time_days: int          # from suppliers.csv

    # --- I3 placeholder (safety stock) ---
    safety_stock: float          # = 0 until I3 provides a formal target
    safety_stock_source: str     # "I3_PLACEHOLDER_ZERO" until I3 is live

    # --- I2 computed reorder point ---
    reorder_point: float         # average_daily_demand × lead_time_days + safety_stock

    # --- I2 decision ---
    reorder_needed: bool         # inventory_position <= reorder_point
    suggested_reorder_qty: float # max(0, reorder_point - inventory_position)

    # --- Explanation ---
    reason: str                  # human-readable decision rationale

    # --- Metadata ---
    generated_at: datetime

    def to_dict(self) -> dict:
        return {
            # Identity
            "product_id": self.product_id,
            "sku": self.sku,
            "product_name": self.product_name,
            "category": self.category,
            "store_id": self.store_id,
            # I1 inputs
            "available_stock": round(self.available_stock, 2),
            "in_transit": round(self.in_transit, 2),
            # I2 position
            "inventory_position": round(self.inventory_position, 2),
            # Demand forecast
            "average_daily_demand": round(self.average_daily_demand, 4),
            "demand_forecast": round(self.demand_forecast, 2),
            "forecast_horizon": self.forecast_horizon,
            "forecast_confidence": round(self.forecast_confidence, 4),
            # Supplier
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "lead_time_days": self.lead_time_days,
            # Safety stock (I3 placeholder)
            "safety_stock": round(self.safety_stock, 2),
            "safety_stock_source": self.safety_stock_source,
            # Reorder point calculation
            "reorder_point": round(self.reorder_point, 4),
            # Decision
            "reorder_needed": self.reorder_needed,
            "suggested_reorder_qty": round(self.suggested_reorder_qty, 2),
            # Explanation
            "reason": self.reason,
            # Metadata
            "generated_at": self.generated_at.isoformat(),
        }
