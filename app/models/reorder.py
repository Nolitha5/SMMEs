"""Reorder suggestion model — derived from I1 stock status + demand forecast."""
from dataclasses import dataclass


@dataclass
class ReorderSuggestion:
    """
    A suggested replenishment action for an understocked product.

    Suggested quantity = expected_7d_demand - (available_stock + in_transit)
    clamped to >= 1.
    """

    product_id: str
    product_name: str
    sku: str
    category: str
    store_id: str
    available_stock: float
    in_transit: float
    expected_7d_demand: float
    net_shortage: float         # expected_7d_demand - (available + in_transit)
    suggested_order_qty: float
    unit_cost: float
    estimated_order_cost: float
    priority: str               # URGENT / HIGH / NORMAL

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "sku": self.sku,
            "category": self.category,
            "store_id": self.store_id,
            "available_stock": self.available_stock,
            "in_transit": self.in_transit,
            "expected_7d_demand": self.expected_7d_demand,
            "net_shortage": round(self.net_shortage, 1),
            "suggested_order_qty": self.suggested_order_qty,
            "unit_cost": self.unit_cost,
            "estimated_order_cost": round(self.estimated_order_cost, 2),
            "priority": self.priority,
        }
