"""Product domain model — aligned to shared mock retail dataset schema."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    """
    Represents a product/SKU from the shared dataset.

    Shared schema:
        product_id, sku, name, category, unit_cost, sell_price,
        margin_floor, shelf_life_days, active
    """

    product_id: str
    sku: str
    name: str
    category: str
    unit_cost: float
    sell_price: float
    margin_floor: float
    shelf_life_days: Optional[int]  # None means non-perishable
    active: bool

    @property
    def is_perishable(self) -> bool:
        """Products with shelf_life_days <= 30 are considered perishable."""
        return self.shelf_life_days is not None and self.shelf_life_days <= 30

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "category": self.category,
            "unit_cost": self.unit_cost,
            "sell_price": self.sell_price,
            "margin_floor": self.margin_floor,
            "shelf_life_days": self.shelf_life_days,
            "active": self.active,
            "is_perishable": self.is_perishable,
        }
