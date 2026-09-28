"""
DataLoader — reads all shared mock retail dataset files locally.
Uses only Python stdlib (csv, json, pathlib). No external dependencies.
"""
import csv
import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from app.models import (
    DemandForecast,
    InventoryMovement,
    InventorySnapshot,
    MovementType,
    Product,
    Supplier,
    SupplierPerformance,
    Transaction,
)


class DataLoader:
    """
    Reads the shared dataset CSV/JSON files from a local data directory.

    File mapping:
        products.csv              → load_products()
        inventory_snapshots.csv   → load_inventory_snapshots()
        inventory_movements.csv   → load_inventory_movements()
        transactions.csv          → load_transactions()
        demand_forecasts.json     → load_demand_forecasts()
        suppliers.csv             → load_suppliers()
        supplier_performance.csv  → load_supplier_performance()
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._config = self._load_config()

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        config_path = self.data_dir / "config.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    @property
    def config(self) -> dict:
        return self._config

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def load_products(self) -> Dict[str, Product]:
        """
        Returns {product_id: Product}.

        Shared schema:
            product_id, sku, name, category, unit_cost, sell_price,
            margin_floor, shelf_life_days, active
        """
        path = self.data_dir / "products.csv"
        products: Dict[str, Product] = {}
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                shelf_life = row.get("shelf_life_days", "").strip()
                p = Product(
                    product_id=row["product_id"].strip(),
                    sku=row["sku"].strip(),
                    name=row["name"].strip(),
                    category=row["category"].strip(),
                    unit_cost=float(row["unit_cost"]),
                    sell_price=float(row["sell_price"]),
                    margin_floor=float(row["margin_floor"]),
                    shelf_life_days=int(shelf_life) if shelf_life else None,
                    active=row["active"].strip().lower() == "true",
                )
                products[p.product_id] = p
        return products

    # ------------------------------------------------------------------
    # Inventory snapshots
    # ------------------------------------------------------------------

    def load_inventory_snapshots(self) -> List[InventorySnapshot]:
        """
        Returns all InventorySnapshot records, all timestamps.

        Shared schema:
            timestamp, store_id, product_id, stock_on_hand, reserved,
            damaged, in_transit

        I1 uses: available_stock = stock_on_hand - reserved - damaged
        """
        path = self.data_dir / "inventory_snapshots.csv"
        snapshots: List[InventorySnapshot] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                s = InventorySnapshot(
                    timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                    store_id=row["store_id"].strip(),
                    product_id=row["product_id"].strip(),
                    stock_on_hand=float(row["stock_on_hand"]),
                    reserved=float(row["reserved"]),
                    damaged=float(row["damaged"]),
                    in_transit=float(row["in_transit"]),
                )
                snapshots.append(s)
        return snapshots

    # ------------------------------------------------------------------
    # Inventory movements
    # ------------------------------------------------------------------

    def load_inventory_movements(self) -> List[InventoryMovement]:
        """
        Returns all InventoryMovement records.

        Shared schema:
            movement_id, product_id, type, qty, timestamp, reference
        """
        path = self.data_dir / "inventory_movements.csv"
        movements: List[InventoryMovement] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                raw_type = row["type"].strip().upper()
                try:
                    mv_type = MovementType(raw_type)
                except ValueError:
                    mv_type = MovementType.ADJUSTMENT   # safe fallback

                m = InventoryMovement(
                    movement_id=row["movement_id"].strip(),
                    product_id=row["product_id"].strip(),
                    movement_type=mv_type,
                    qty=float(row["qty"]),
                    timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                    reference=row.get("reference", "").strip() or None,
                )
                movements.append(m)
        return movements

    # ------------------------------------------------------------------
    # Transactions (sales)
    # ------------------------------------------------------------------

    def load_transactions(self) -> List[Transaction]:
        """
        Returns all Transaction records (sales).

        Shared schema:
            transaction_id, timestamp, store_id, product_id, qty,
            unit_price, discount
        """
        path = self.data_dir / "transactions.csv"
        txns: List[Transaction] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                t = Transaction(
                    transaction_id=row["transaction_id"].strip(),
                    timestamp=datetime.fromisoformat(row["timestamp"].strip()),
                    store_id=row["store_id"].strip(),
                    product_id=row["product_id"].strip(),
                    qty=float(row["qty"]),
                    unit_price=float(row["unit_price"]),
                    discount=float(row["discount"]),
                )
                txns.append(t)
        return txns

    # ------------------------------------------------------------------
    # Demand forecasts  (Demand → Inventory contract)
    # ------------------------------------------------------------------

    def load_demand_forecasts(self) -> Dict[str, DemandForecast]:
        """
        Returns {product_id: DemandForecast} from demand_forecasts.json.

        Shared contract:
            product_id, horizon, expected_qty, lower_bound, upper_bound,
            confidence, drivers, generated_at, source

        I1 reads this contract; it does NOT generate forecasts.
        The source field will be "mock_demand_forecast" until Member 1's
        real model output replaces this file.
        """
        path = self.data_dir / "demand_forecasts.json"
        forecasts: Dict[str, DemandForecast] = {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("demand_forecasts.json must contain a JSON array")

        for item in data:
            fc = DemandForecast(
                product_id=item["product_id"],
                horizon=int(item["horizon"]),
                expected_qty=float(item["expected_qty"]),
                lower_bound=float(item["lower_bound"]),
                upper_bound=float(item["upper_bound"]),
                confidence=float(item["confidence"]),
                drivers=list(item.get("drivers", [])),
                generated_at=datetime.fromisoformat(item["generated_at"]),
                source=item.get("source", "mock_demand_forecast"),
            )
            forecasts[fc.product_id] = fc
        return forecasts

    # ------------------------------------------------------------------
    # Suppliers (loaded for I2/I3 future use)
    # ------------------------------------------------------------------

    def load_suppliers(self) -> Dict[str, Supplier]:
        """
        Returns {supplier_id: Supplier}.

        Shared schema:
            supplier_id, name, category, lead_time_days, reliability_score
        """
        path = self.data_dir / "suppliers.csv"
        suppliers: Dict[str, Supplier] = {}
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                s = Supplier(
                    supplier_id=row["supplier_id"].strip(),
                    name=row["name"].strip(),
                    category=row["category"].strip(),
                    lead_time_days=int(row["lead_time_days"]),
                    reliability_score=float(row["reliability_score"]),
                )
                suppliers[s.supplier_id] = s
        return suppliers

    def load_supplier_performance(self) -> List[SupplierPerformance]:
        """
        Returns all SupplierPerformance records.

        Shared schema:
            performance_id, supplier_id, period_end, orders,
            on_time_orders, on_time_rate
        """
        path = self.data_dir / "supplier_performance.csv"
        records: List[SupplierPerformance] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                r = SupplierPerformance(
                    performance_id=row["performance_id"].strip(),
                    supplier_id=row["supplier_id"].strip(),
                    period_end=date.fromisoformat(row["period_end"].strip()),
                    orders=int(row["orders"]),
                    on_time_orders=int(row["on_time_orders"]),
                    on_time_rate=float(row["on_time_rate"]),
                )
                records.append(r)
        return records
