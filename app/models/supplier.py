"""
Supplier domain models — loaded for future I2/I3 use.
Not used by I1 Stock Monitor directly.

Shared suppliers.csv:
    supplier_id, name, category, lead_time_days, reliability_score

Shared supplier_performance.csv:
    performance_id, supplier_id, period_end, orders, on_time_orders, on_time_rate
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class Supplier:
    supplier_id: str
    name: str
    category: str
    lead_time_days: int
    reliability_score: float

    def to_dict(self) -> dict:
        return {
            "supplier_id": self.supplier_id,
            "name": self.name,
            "category": self.category,
            "lead_time_days": self.lead_time_days,
            "reliability_score": self.reliability_score,
        }


@dataclass
class SupplierPerformance:
    performance_id: str
    supplier_id: str
    period_end: date
    orders: int
    on_time_orders: int
    on_time_rate: float

    def to_dict(self) -> dict:
        return {
            "performance_id": self.performance_id,
            "supplier_id": self.supplier_id,
            "period_end": self.period_end.isoformat(),
            "orders": self.orders,
            "on_time_orders": self.on_time_orders,
            "on_time_rate": self.on_time_rate,
        }
