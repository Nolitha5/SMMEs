"""
InventorySnapshot domain model — aligned to shared mock retail dataset schema.

Replaces the old StockLevel model (warehouse_id → store_id).
The old name StockLevel is kept as an alias for backward-compat in imports.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class InventorySnapshot:
    """
    Represents a point-in-time stock record for a product at a store.

    Shared schema:
        timestamp, store_id, product_id, stock_on_hand, reserved, damaged, in_transit

    I1 formula:
        available_stock = stock_on_hand - reserved - damaged
    """

    timestamp: datetime
    store_id: str
    product_id: str
    stock_on_hand: float
    reserved: float
    damaged: float
    in_transit: float

    @property
    def available_stock(self) -> float:
        """
        Net available stock for sale / use.
        Negative values are clamped to 0 for status classification,
        but the raw value is preserved for reporting.
        """
        return self.stock_on_hand - self.reserved - self.damaged

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "store_id": self.store_id,
            "product_id": self.product_id,
            "stock_on_hand": self.stock_on_hand,
            "reserved": self.reserved,
            "damaged": self.damaged,
            "in_transit": self.in_transit,
            "available_stock": self.available_stock,
        }


# Backward-compatible alias used by some router imports
StockLevel = InventorySnapshot
