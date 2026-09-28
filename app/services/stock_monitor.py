"""
I1 Stock Monitor — core business logic.

I1 is responsible for:
  - Loading the latest inventory snapshot per (store, product)
  - Computing available_stock = stock_on_hand - reserved - damaged
  - Classifying stock status (HEALTHY / LOW / STOCK_PRESSURE / CRITICAL / OUT_OF_STOCK)
  - Computing days_of_supply as a monitoring metric (NOT a reorder decision)
  - Producing InventoryPosition objects — the formal I1 output contract
  - Generating alerts for non-HEALTHY stock conditions
  - Reading DemandForecast data for context and to supply to I2

I1 is NOT responsible for:
  - Calculating the reorder point            → I2 Reorder Point Agent
  - Deciding whether to reorder              → I2
  - Calculating safety stock                 → I3
  - Expiry / slow-stock analysis             → I4
  - Exception detection                      → I5

Classification rules (days_of_supply = available / daily_demand_rate):
  OUT_OF_STOCK   : available_stock <= 0
  CRITICAL       : 0 < days < CRITICAL_DAYS (default 2)
  STOCK_PRESSURE : CRITICAL_DAYS <= days < LOW_DAYS  AND
                   (available + in_transit) < forecast_7d_demand
  LOW            : CRITICAL_DAYS <= days < LOW_DAYS  (pressure eased by in_transit)
  HEALTHY        : days >= LOW_DAYS

No LLM, no external APIs, no database — fully offline.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models import (
    Alert,
    AlertSeverity,
    AlertType,
    DemandForecast,
    InventoryMovement,
    InventoryPosition,
    InventorySnapshot,
    Product,
    StockStatus,
    Supplier,
    SupplierPerformance,
    Transaction,
)
from app.models.alert import STATUS_ALERT_TYPE_MAP, STATUS_SEVERITY_MAP
from app.services.data_loader import DataLoader

DEFAULT_CRITICAL_DAYS = 2.0
DEFAULT_LOW_DAYS = 7.0
DEFAULT_NO_FORECAST_CRITICAL = 5.0
DEFAULT_NO_FORECAST_LOW = 15.0


class StockMonitor:
    """I1 Stock Monitor engine."""

    def __init__(self, data_dir: Path):
        self._loader = DataLoader(data_dir)
        cfg = self._loader.config
        th = cfg.get("thresholds", {})
        self._critical_days: float = th.get("critical_days", DEFAULT_CRITICAL_DAYS)
        self._low_days: float = th.get("low_days", DEFAULT_LOW_DAYS)
        self._no_fc_critical: float = th.get("no_forecast_critical_units", DEFAULT_NO_FORECAST_CRITICAL)
        self._no_fc_low: float = th.get("no_forecast_low_units", DEFAULT_NO_FORECAST_LOW)
        self._reload()

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _reload(self):
        self._products: Dict[str, Product] = self._loader.load_products()
        self._snapshots: List[InventorySnapshot] = self._loader.load_inventory_snapshots()
        self._movements: List[InventoryMovement] = self._loader.load_inventory_movements()
        self._transactions: List[Transaction] = self._loader.load_transactions()
        self._forecasts: Dict[str, DemandForecast] = self._loader.load_demand_forecasts()
        self._suppliers: Dict[str, Supplier] = self._loader.load_suppliers()
        self._supplier_perf: List[SupplierPerformance] = self._loader.load_supplier_performance()

        # Latest snapshot index: (store_id, product_id) → InventorySnapshot
        latest: Dict[Tuple[str, str], InventorySnapshot] = {}
        for s in self._snapshots:
            key = (s.store_id, s.product_id)
            if key not in latest or s.timestamp > latest[key].timestamp:
                latest[key] = s
        self._latest_snapshots = latest
        self._stores = sorted({s.store_id for s in self._snapshots})
        self._loaded_at = datetime.now()

    def reload(self):
        self._reload()

    # ------------------------------------------------------------------
    # Internal: classification  (I1 monitoring — NOT reorder decisions)
    # ------------------------------------------------------------------

    def _days_of_supply(self, available: float, forecast: Optional[DemandForecast]) -> Optional[float]:
        """
        Monitoring metric: how many days the current available stock will last
        at the forecast daily demand rate.

        Returns None when demand rate is zero (no demand expected).
        This value is included in InventoryPosition for I2 to use; I1 does
        NOT use it to calculate a reorder point or a reorder quantity.
        """
        if forecast is None or forecast.daily_rate <= 0:
            return None
        return available / forecast.daily_rate

    def _classify_stock(
        self,
        snapshot: InventorySnapshot,
        forecast: Optional[DemandForecast],
    ) -> Tuple[StockStatus, Optional[float]]:
        """
        Returns (StockStatus, days_of_supply).

        Classification uses days_of_supply as a monitoring threshold only.
        The actual reorder-point threshold is I2's responsibility.
        """
        available = snapshot.available_stock
        in_transit = snapshot.in_transit
        expected_qty = forecast.expected_qty if forecast else 0.0

        if forecast is None:
            # Fallback: unit thresholds when no forecast is available
            if available <= 0:
                return StockStatus.OUT_OF_STOCK, None
            elif available < self._no_fc_critical:
                return StockStatus.CRITICAL, None
            elif available < self._no_fc_low:
                return StockStatus.LOW, None
            else:
                return StockStatus.HEALTHY, None

        dos = self._days_of_supply(available, forecast)

        if available <= 0:
            return StockStatus.OUT_OF_STOCK, dos
        elif dos is not None and dos < self._critical_days:
            return StockStatus.CRITICAL, dos
        elif dos is not None and dos < self._low_days:
            # Distinguish STOCK_PRESSURE (in_transit won't cover demand)
            # from LOW (in_transit makes up the shortfall)
            if (available + in_transit) < expected_qty:
                return StockStatus.STOCK_PRESSURE, dos
            else:
                return StockStatus.LOW, dos
        else:
            return StockStatus.HEALTHY, dos

    # ------------------------------------------------------------------
    # Public API — InventoryPosition (formal I1 output for I2)
    # ------------------------------------------------------------------

    def get_inventory_positions(
        self, store_id: Optional[str] = None
    ) -> List[InventoryPosition]:
        """
        Build and return InventoryPosition objects for all active products.

        This is the primary I1 output contract. I2 (Reorder Point Agent)
        will consume these objects to decide whether a reorder is needed.

        I1 includes forecast_7d_demand and forecast_confidence as context
        fields for I2 — I1 does NOT use them to calculate a reorder point.
        """
        positions: List[InventoryPosition] = []
        snapshots = list(self._latest_snapshots.values())
        if store_id:
            snapshots = [s for s in snapshots if s.store_id == store_id]

        for snap in snapshots:
            product = self._products.get(snap.product_id)
            if not product or not product.active:
                continue

            forecast = self._forecasts.get(snap.product_id)
            status, dos = self._classify_stock(snap, forecast)

            positions.append(InventoryPosition(
                product_id=product.product_id,
                sku=product.sku,
                product_name=product.name,
                category=product.category,
                store_id=snap.store_id,
                snapshot_timestamp=snap.timestamp,
                stock_on_hand=snap.stock_on_hand,
                reserved=snap.reserved,
                damaged=snap.damaged,
                in_transit=snap.in_transit,
                available_stock=snap.available_stock,
                stock_status=status,
                days_of_supply=dos,
                needs_attention=(status != StockStatus.HEALTHY),
                forecast_7d_demand=forecast.expected_qty if forecast else 0.0,
                forecast_confidence=forecast.confidence if forecast else 0.0,
                forecast_source=forecast.source if forecast else "none",
            ))

        positions.sort(
            key=lambda p: (
                {
                    StockStatus.OUT_OF_STOCK: 0,
                    StockStatus.CRITICAL: 1,
                    StockStatus.STOCK_PRESSURE: 2,
                    StockStatus.LOW: 3,
                    StockStatus.HEALTHY: 4,
                }.get(p.stock_status, 9),
                p.product_id,
            )
        )
        return positions

    # ------------------------------------------------------------------
    # Public API — Products
    # ------------------------------------------------------------------

    def get_all_products(self) -> List[dict]:
        return [p.to_dict() for p in self._products.values() if p.active]

    def get_product(self, product_id: str):
        p = self._products.get(product_id)
        return p.to_dict() if p else None

    def get_products_by_category(self, category: str) -> List[dict]:
        return [
            p.to_dict()
            for p in self._products.values()
            if p.category.lower() == category.lower() and p.active
        ]

    # ------------------------------------------------------------------
    # Public API — Stock summary (convenience view over InventoryPosition)
    # ------------------------------------------------------------------

    def get_stock_summary(self, store_id: Optional[str] = None) -> List[dict]:
        """
        Returns the current inventory position for all active products as dicts.
        Delegates to get_inventory_positions() and adds convenience fields used
        by the REST layer: 'severity' (AlertSeverity string) and
        'expected_7d_demand' (alias for forecast_7d_demand).
        """
        rows = []
        for pos in self.get_inventory_positions(store_id=store_id):
            d = pos.to_dict()
            d["severity"] = STATUS_SEVERITY_MAP[pos.stock_status].value
            d["expected_7d_demand"] = d["forecast_7d_demand"]
            rows.append(d)
        return rows

    def get_stock_for_product(self, product_id: str) -> List[dict]:
        """All historical snapshots for one product with I1 classification."""
        result = []
        forecast = self._forecasts.get(product_id)
        for snap in self._snapshots:
            if snap.product_id != product_id:
                continue
            status, dos = self._classify_stock(snap, forecast)
            d = snap.to_dict()
            d["stock_status"] = status.value
            d["days_of_supply"] = round(dos, 2) if dos is not None else None
            result.append(d)
        result.sort(key=lambda r: r["timestamp"], reverse=True)
        return result

    # ------------------------------------------------------------------
    # Public API — Alerts
    # ------------------------------------------------------------------

    def generate_alerts(
        self,
        store_id: Optional[str] = None,
        severity_filter: Optional[str] = None,
    ) -> List[dict]:
        """
        Scan the latest inventory positions and return active alerts.
        HEALTHY positions generate no alert.

        I1 flags that attention is needed; the reorder decision is I2's.
        """
        severity_rank = {
            AlertSeverity.CRITICAL: 4,
            AlertSeverity.HIGH: 3,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 1,
            AlertSeverity.INFO: 0,
        }
        min_rank = 0
        if severity_filter:
            try:
                min_rank = severity_rank[AlertSeverity(severity_filter.upper())]
            except ValueError:
                pass

        alerts: List[Alert] = []
        now = datetime.now()

        positions = self.get_inventory_positions(store_id=store_id)
        for pos in positions:
            if pos.stock_status == StockStatus.HEALTHY:
                continue

            severity = STATUS_SEVERITY_MAP[pos.stock_status]
            if severity_rank[severity] < min_rank:
                continue

            alert_type = STATUS_ALERT_TYPE_MAP.get(pos.stock_status, AlertType.LOW_STOCK)
            message = self._build_message(pos)

            snap = self._latest_snapshots.get((pos.store_id, pos.product_id))

            alerts.append(Alert(
                alert_id=f"I1-{uuid.uuid4().hex[:8].upper()}",
                product_id=pos.product_id,
                product_name=pos.product_name,
                store_id=pos.store_id,
                stock_status=pos.stock_status,
                alert_type=alert_type,
                severity=severity,
                message=message,
                available_stock=pos.available_stock,
                stock_on_hand=pos.stock_on_hand,
                reserved=pos.reserved,
                damaged=pos.damaged,
                in_transit=pos.in_transit,
                days_of_supply=pos.days_of_supply if pos.days_of_supply is not None else -1,
                expected_7d_demand=pos.forecast_7d_demand,
                generated_at=now,
            ))

        alerts.sort(key=lambda a: -severity_rank[a.severity])
        return [a.to_dict() for a in alerts]

    def _build_message(self, pos: InventoryPosition) -> str:
        name = pos.product_name
        store = pos.store_id
        avail = pos.available_stock
        dos_str = f"{pos.days_of_supply:.1f}d" if pos.days_of_supply is not None else "unknown"
        demand = pos.forecast_7d_demand

        messages = {
            StockStatus.OUT_OF_STOCK: (
                f"OUT OF STOCK: {name} @ {store} — available_stock={avail:.0f} "
                f"(on_hand={pos.stock_on_hand:.0f}, reserved={pos.reserved:.0f}, "
                f"damaged={pos.damaged:.0f}). Replenishment attention required."
            ),
            StockStatus.CRITICAL: (
                f"CRITICAL: {name} @ {store} — {avail:.0f} units available, "
                f"{dos_str} of supply vs 7d context demand of {demand:.0f}. "
                f"Replenishment attention required."
            ),
            StockStatus.STOCK_PRESSURE: (
                f"STOCK PRESSURE: {name} @ {store} — {avail:.0f} units available + "
                f"{pos.in_transit:.0f} in transit, insufficient for 7d context demand "
                f"({demand:.0f}). Days of supply: {dos_str}."
            ),
            StockStatus.LOW: (
                f"LOW STOCK: {name} @ {store} — {avail:.0f} units available ({dos_str} of supply). "
                f"In-transit {pos.in_transit:.0f} may cover 7d context demand of {demand:.0f}."
            ),
        }
        return messages.get(pos.stock_status, f"Stock condition flagged for {name} @ {store}.")

    # ------------------------------------------------------------------
    # Public API — Demand forecasts (read-only; I2 will consume for reorder calc)
    # ------------------------------------------------------------------

    def get_demand_forecasts(self, product_id: Optional[str] = None) -> List[dict]:
        """
        Read-only view of demand_forecasts.json.

        I1 reads this file to populate forecast_7d_demand in InventoryPosition
        so that I2 has the context it needs. I1 does NOT use this data to
        calculate a reorder point.
        """
        forecasts = list(self._forecasts.values())
        if product_id:
            forecasts = [f for f in forecasts if f.product_id == product_id]
        return [f.to_dict() for f in forecasts]

    # ------------------------------------------------------------------
    # Public API — Transactions and movements
    # ------------------------------------------------------------------

    def get_transactions(
        self,
        product_id: Optional[str] = None,
        store_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        txns = self._transactions
        if product_id:
            txns = [t for t in txns if t.product_id == product_id]
        if store_id:
            txns = [t for t in txns if t.store_id == store_id]
        txns = sorted(txns, key=lambda t: t.timestamp, reverse=True)
        return [t.to_dict() for t in txns[:limit]]

    def get_movements(
        self,
        product_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        movs = self._movements
        if product_id:
            movs = [m for m in movs if m.product_id == product_id]
        movs = sorted(movs, key=lambda m: m.timestamp, reverse=True)
        return [m.to_dict() for m in movs[:limit]]

    # ------------------------------------------------------------------
    # Public API — Suppliers (loaded; consumed by I2/I3)
    # ------------------------------------------------------------------

    def get_suppliers(self) -> List[dict]:
        return [s.to_dict() for s in self._suppliers.values()]

    def get_supplier_performance(self) -> List[dict]:
        return [p.to_dict() for p in self._supplier_perf]

    # ------------------------------------------------------------------
    # Public API — Dashboard
    # ------------------------------------------------------------------

    def get_dashboard(self) -> dict:
        """I1 monitoring dashboard — stock health KPIs only. No reorder decisions."""
        positions = self.get_inventory_positions()

        status_counts: Dict[str, int] = defaultdict(int)
        for pos in positions:
            status_counts[pos.stock_status.value] += 1

        healthy = status_counts.get(StockStatus.HEALTHY.value, 0)
        needs_attention = sum(
            v for k, v in status_counts.items() if k != StockStatus.HEALTHY.value
        )

        alerts = self.generate_alerts()
        severity_counts: Dict[str, int] = defaultdict(int)
        for a in alerts:
            severity_counts[a["severity"]] += 1

        return {
            "generated_at": datetime.now().isoformat(),
            "data_loaded_at": self._loaded_at.isoformat(),
            "module": "I1 Stock Monitor",
            "stores": self._stores,
            "total_active_products": sum(1 for p in self._products.values() if p.active),
            "total_snapshot_records": len(self._latest_snapshots),
            "demand_forecast_source": (
                list(self._forecasts.values())[0].source if self._forecasts else "none"
            ),
            "stock_health": {
                "healthy": healthy,
                "needs_attention": needs_attention,
                "by_status": dict(status_counts),
            },
            "alerts": {
                "total": len(alerts),
                "by_severity": dict(severity_counts),
            },
            # NOTE: reorder_suggestions are NOT an I1 responsibility.
            # I2 (Reorder Point Agent) will produce ReorderNeed outputs.
            "i2_note": "Reorder point calculation and reorder decisions belong to I2.",
        }
