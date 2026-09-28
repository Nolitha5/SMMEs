"""
Transaction domain models — aligned to shared mock retail dataset schema.

Shared transactions.csv schema:
    transaction_id, timestamp, store_id, product_id, qty, unit_price, discount

Shared inventory_movements.csv schema:
    movement_id, product_id, type, qty, timestamp, reference
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MovementType(str, Enum):
    RECEIPT = "RECEIPT"
    SALE = "SALE"
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"
    TRANSFER = "TRANSFER"
    RETURN = "RETURN"


@dataclass
class Transaction:
    """
    A point-of-sale / retail transaction (sales record).

    Shared schema: transaction_id, timestamp, store_id, product_id,
                   qty, unit_price, discount
    """

    transaction_id: str
    timestamp: datetime
    store_id: str
    product_id: str
    qty: float
    unit_price: float
    discount: float

    @property
    def revenue(self) -> float:
        return self.qty * self.unit_price * (1 - self.discount)

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "store_id": self.store_id,
            "product_id": self.product_id,
            "qty": self.qty,
            "unit_price": self.unit_price,
            "discount": self.discount,
            "revenue": round(self.revenue, 2),
        }


@dataclass
class InventoryMovement:
    """
    A stock movement or adjustment event (supply chain / warehouse record).

    Shared schema: movement_id, product_id, type, qty, timestamp, reference
    """

    movement_id: str
    product_id: str
    movement_type: MovementType
    qty: float          # positive = into stock, negative = out of stock
    timestamp: datetime
    reference: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "movement_id": self.movement_id,
            "product_id": self.product_id,
            "movement_type": self.movement_type.value,
            "qty": self.qty,
            "timestamp": self.timestamp.isoformat(),
            "reference": self.reference,
        }
