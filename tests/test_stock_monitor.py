"""
Unit tests for I1 Stock Monitor — shared mock retail dataset.

Run with: python -m pytest tests/ -v

Tests verify:
- All shared dataset files are loaded correctly
- I1 available_stock = stock_on_hand - reserved - damaged
- Stock classification (OUT_OF_STOCK, CRITICAL, STOCK_PRESSURE, LOW, HEALTHY)
- Known intentional scenarios from the dataset README
- InventoryPosition output contract (I1 → I2 handoff)
- Demand forecast contract is readable
- Dashboard KPIs are consistent
- Alerts are generated correctly
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.services.stock_monitor import StockMonitor
from app.models.alert import StockStatus
from app.models.inventory_position import InventoryPosition

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def monitor():
    return StockMonitor(data_dir=DATA_DIR)


# ------------------------------------------------------------------
# 1. Data loading
# ------------------------------------------------------------------

class TestDataLoading:
    def test_products_loaded(self, monitor):
        products = monitor.get_all_products()
        assert len(products) == 20, f"Expected 20 active products, got {len(products)}"

    def test_product_schema(self, monitor):
        p = monitor.get_product("P001")
        assert p is not None
        assert p["name"] == "White Bread 700g"
        assert p["sku"] == "SKU-001"
        assert p["category"] == "Bakery"
        assert p["shelf_life_days"] == 3
        assert p["active"] is True

    def test_product_not_found(self, monitor):
        assert monitor.get_product("XXXX") is None

    def test_snapshots_loaded(self, monitor):
        # 20 products × 5 weekly timestamps = 100 snapshot rows
        assert len(monitor._snapshots) == 100

    def test_latest_snapshots_index(self, monitor):
        # One latest record per (store, product)
        assert len(monitor._latest_snapshots) == 20

    def test_movements_loaded(self, monitor):
        assert len(monitor._movements) == 25   # 25 movement records

    def test_transactions_loaded(self, monitor):
        assert len(monitor._transactions) == 600

    def test_demand_forecasts_loaded(self, monitor):
        forecasts = monitor.get_demand_forecasts()
        assert len(forecasts) == 20
        pids = {f["product_id"] for f in forecasts}
        assert "P001" in pids
        assert "P020" in pids

    def test_demand_forecast_schema(self, monitor):
        forecasts = monitor.get_demand_forecasts(product_id="P001")
        assert len(forecasts) == 1
        fc = forecasts[0]
        assert fc["horizon"] == 7
        assert fc["expected_qty"] > 0
        assert 0 < fc["confidence"] <= 1
        assert fc["source"] == "mock_demand_forecast"
        assert "daily_rate" in fc

    def test_suppliers_loaded(self, monitor):
        suppliers = monitor.get_suppliers()
        assert len(suppliers) >= 1

    def test_supplier_performance_loaded(self, monitor):
        perf = monitor.get_supplier_performance()
        assert len(perf) >= 1


# ------------------------------------------------------------------
# 2. available_stock formula
# ------------------------------------------------------------------

class TestAvailableStockFormula:
    def test_available_stock_formula(self, monitor):
        """available_stock = stock_on_hand - reserved - damaged"""
        for snap in monitor._snapshots:
            expected = snap.stock_on_hand - snap.reserved - snap.damaged
            assert snap.available_stock == pytest.approx(expected), (
                f"Failed for {snap.product_id}: "
                f"on_hand={snap.stock_on_hand}, reserved={snap.reserved}, "
                f"damaged={snap.damaged}"
            )

    def test_p001_latest_out_of_stock(self, monitor):
        """P001 latest: stock_on_hand=0, reserved=0, damaged=1 → available=-1"""
        snap = monitor._latest_snapshots.get(("STORE-001", "P001"))
        assert snap is not None
        assert snap.stock_on_hand == 0
        assert snap.damaged == 1
        assert snap.available_stock == pytest.approx(-1.0)

    def test_p002_latest_low(self, monitor):
        """P002 latest: stock_on_hand=2, reserved=1 → available=1"""
        snap = monitor._latest_snapshots.get(("STORE-001", "P002"))
        assert snap is not None
        assert snap.available_stock == pytest.approx(1.0)


# ------------------------------------------------------------------
# 3. Stock classification — intentional dataset scenarios
# ------------------------------------------------------------------

class TestStockClassification:
    def _get_status(self, monitor, product_id) -> StockStatus:
        snap = monitor._latest_snapshots.get(("STORE-001", product_id))
        forecast = monitor._forecasts.get(product_id)
        status, _ = monitor._classify_stock(snap, forecast)
        return status

    def test_p001_out_of_stock(self, monitor):
        """P001: available=-1 → OUT_OF_STOCK (highest priority)"""
        assert self._get_status(monitor, "P001") == StockStatus.OUT_OF_STOCK

    def test_p002_critical_or_pressure(self, monitor):
        """P002: available=1, 7d demand=19 → CRITICAL (days_of_supply < 2)"""
        status = self._get_status(monitor, "P002")
        assert status in (StockStatus.CRITICAL, StockStatus.STOCK_PRESSURE)

    def test_p014_low_or_pressure(self, monitor):
        """P014: available=1, in_transit=12, 7d demand=8 → STOCK_PRESSURE or LOW"""
        status = self._get_status(monitor, "P014")
        assert status in (StockStatus.CRITICAL, StockStatus.STOCK_PRESSURE, StockStatus.LOW)

    def test_p016_low_or_critical(self, monitor):
        """P016: available=1, in_transit=0, 7d demand=8 → CRITICAL or STOCK_PRESSURE"""
        status = self._get_status(monitor, "P016")
        assert status in (StockStatus.CRITICAL, StockStatus.STOCK_PRESSURE)

    def test_p004_healthy(self, monitor):
        """P004: available=38, 7d demand=7 → HEALTHY"""
        assert self._get_status(monitor, "P004") == StockStatus.HEALTHY

    def test_p010_healthy(self, monitor):
        """P010: available=56, 7d demand=15 → HEALTHY"""
        assert self._get_status(monitor, "P010") == StockStatus.HEALTHY

    def test_p020_healthy(self, monitor):
        """P020: available=68, 7d demand=20 → HEALTHY"""
        assert self._get_status(monitor, "P020") == StockStatus.HEALTHY


# ------------------------------------------------------------------
# 4. Stock summary API
# ------------------------------------------------------------------

class TestStockSummary:
    def test_stock_summary_returns_all_products(self, monitor):
        summary = monitor.get_stock_summary()
        assert len(summary) == 20

    def test_stock_summary_has_required_fields(self, monitor):
        summary = monitor.get_stock_summary()
        required = {
            "product_id", "product_name", "sku", "category",
            "store_id", "stock_on_hand", "reserved", "damaged",
            "in_transit", "available_stock", "stock_status",
            "severity", "days_of_supply", "expected_7d_demand",
        }
        for row in summary:
            missing = required - set(row.keys())
            assert not missing, f"Missing fields in summary row: {missing}"

    def test_store_filter(self, monitor):
        summary = monitor.get_stock_summary(store_id="STORE-001")
        for row in summary:
            assert row["store_id"] == "STORE-001"

    def test_summary_sorted_severity_first(self, monitor):
        """Most severe items must appear first."""
        summary = monitor.get_stock_summary()
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        ranks = [severity_order.get(r["severity"], 9) for r in summary]
        assert ranks == sorted(ranks)


# ------------------------------------------------------------------
# 5. Alerts
# ------------------------------------------------------------------

class TestAlerts:
    def test_alerts_generated(self, monitor):
        alerts = monitor.generate_alerts()
        assert len(alerts) > 0

    def test_critical_alerts_exist(self, monitor):
        alerts = monitor.generate_alerts(severity_filter="CRITICAL")
        assert len(alerts) > 0
        for a in alerts:
            assert a["severity"] == "CRITICAL"

    def test_alert_schema(self, monitor):
        alerts = monitor.generate_alerts()
        required = {
            "alert_id", "product_id", "product_name", "store_id",
            "stock_status", "alert_type", "severity", "message",
            "available_stock", "stock_on_hand", "reserved", "damaged",
            "in_transit", "days_of_supply", "expected_7d_demand",
        }
        for a in alerts:
            missing = required - set(a.keys())
            assert not missing, f"Missing alert fields: {missing}"

    def test_p001_has_out_of_stock_alert(self, monitor):
        alerts = monitor.generate_alerts()
        p001_alerts = [a for a in alerts if a["product_id"] == "P001"]
        assert len(p001_alerts) == 1
        assert p001_alerts[0]["stock_status"] == "OUT_OF_STOCK"

    def test_healthy_products_no_alert(self, monitor):
        """HEALTHY products must not appear in alerts."""
        alerts = monitor.generate_alerts()
        for a in alerts:
            assert a["stock_status"] != "HEALTHY"

    def test_alert_ids_unique(self, monitor):
        alerts = monitor.generate_alerts()
        ids = [a["alert_id"] for a in alerts]
        assert len(ids) == len(set(ids))


# ------------------------------------------------------------------
# 6. InventoryPosition — I1 output contract
# ------------------------------------------------------------------

class TestInventoryPosition:
    def test_positions_returned_for_all_products(self, monitor):
        """get_inventory_positions() must return one position per active product."""
        positions = monitor.get_inventory_positions()
        assert len(positions) == 20

    def test_position_type(self, monitor):
        """All objects must be InventoryPosition instances."""
        positions = monitor.get_inventory_positions()
        for pos in positions:
            assert isinstance(pos, InventoryPosition)

    def test_position_schema(self, monitor):
        """All required fields must be present and non-None."""
        positions = monitor.get_inventory_positions()
        for pos in positions:
            assert pos.product_id
            assert pos.sku
            assert pos.product_name
            assert pos.category
            assert pos.store_id
            assert pos.snapshot_timestamp is not None
            assert isinstance(pos.stock_on_hand, float)
            assert isinstance(pos.available_stock, float)
            assert isinstance(pos.stock_status, StockStatus)
            assert isinstance(pos.needs_attention, bool)
            assert isinstance(pos.forecast_7d_demand, float)
            assert isinstance(pos.forecast_confidence, float)
            assert pos.forecast_source  # must be non-empty

    def test_available_stock_formula_in_position(self, monitor):
        """available_stock in each position = stock_on_hand - reserved - damaged."""
        positions = monitor.get_inventory_positions()
        for pos in positions:
            expected = pos.stock_on_hand - pos.reserved - pos.damaged
            assert pos.available_stock == pytest.approx(expected)

    def test_needs_attention_flag(self, monitor):
        """needs_attention must be True for any non-HEALTHY status."""
        positions = monitor.get_inventory_positions()
        for pos in positions:
            if pos.stock_status == StockStatus.HEALTHY:
                assert pos.needs_attention is False, (
                    f"{pos.product_id} is HEALTHY but needs_attention=True"
                )
            else:
                assert pos.needs_attention is True, (
                    f"{pos.product_id} has status {pos.stock_status} but needs_attention=False"
                )

    def test_p001_out_of_stock_position(self, monitor):
        """P001 must have OUT_OF_STOCK status and needs_attention=True."""
        positions = monitor.get_inventory_positions()
        p001 = next((p for p in positions if p.product_id == "P001"), None)
        assert p001 is not None
        assert p001.stock_status == StockStatus.OUT_OF_STOCK
        assert p001.needs_attention is True

    def test_positions_sorted_by_severity(self, monitor):
        """Most critical positions must appear first."""
        positions = monitor.get_inventory_positions()
        severity_rank = {
            StockStatus.OUT_OF_STOCK: 0,
            StockStatus.CRITICAL: 1,
            StockStatus.STOCK_PRESSURE: 2,
            StockStatus.LOW: 3,
            StockStatus.HEALTHY: 4,
        }
        ranks = [severity_rank[p.stock_status] for p in positions]
        assert ranks == sorted(ranks)

    def test_forecast_fields_passed_through(self, monitor):
        """Forecast fields in InventoryPosition must match demand_forecasts.json."""
        positions = monitor.get_inventory_positions()
        forecasts_by_pid = {
            f["product_id"]: f for f in monitor.get_demand_forecasts()
        }
        for pos in positions:
            fc = forecasts_by_pid.get(pos.product_id)
            if fc:
                assert pos.forecast_7d_demand == pytest.approx(fc["expected_qty"])
                assert pos.forecast_confidence == pytest.approx(fc["confidence"])
                assert pos.forecast_source == fc["source"]

    def test_store_filter(self, monitor):
        """Store filter must return only positions for that store."""
        positions = monitor.get_inventory_positions(store_id="STORE-001")
        for pos in positions:
            assert pos.store_id == "STORE-001"

    def test_to_dict_serialisable(self, monitor):
        """to_dict() must return a dict with all required keys."""
        positions = monitor.get_inventory_positions()
        required = {
            "product_id", "sku", "product_name", "category", "store_id",
            "snapshot_timestamp", "stock_on_hand", "reserved", "damaged",
            "in_transit", "available_stock", "stock_status", "days_of_supply",
            "needs_attention", "forecast_7d_demand", "forecast_confidence",
            "forecast_source",
        }
        for pos in positions:
            d = pos.to_dict()
            missing = required - set(d.keys())
            assert not missing, f"Missing keys in to_dict(): {missing}"

    def test_i1_does_not_include_reorder_qty(self, monitor):
        """InventoryPosition must NOT contain a suggested_order_qty field."""
        positions = monitor.get_inventory_positions()
        for pos in positions:
            d = pos.to_dict()
            assert "suggested_order_qty" not in d
            assert "reorder_qty" not in d
            assert "reorder_point" not in d


# ------------------------------------------------------------------
# 7. Dashboard
# ------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_structure(self, monitor):
        dash = monitor.get_dashboard()
        assert "generated_at" in dash
        assert "total_active_products" in dash
        assert "stock_health" in dash
        assert "alerts" in dash
        assert "demand_forecast_source" in dash

    def test_dashboard_product_count(self, monitor):
        dash = monitor.get_dashboard()
        assert dash["total_active_products"] == 20

    def test_dashboard_forecast_source(self, monitor):
        dash = monitor.get_dashboard()
        assert dash["demand_forecast_source"] == "mock_demand_forecast"

    def test_dashboard_counts_consistent(self, monitor):
        dash = monitor.get_dashboard()
        total_alerts = dash["alerts"]["total"]
        by_severity_sum = sum(dash["alerts"]["by_severity"].values())
        assert by_severity_sum == total_alerts

    def test_dashboard_has_i2_note(self, monitor):
        """Dashboard must signal that reorder decisions belong to I2."""
        dash = monitor.get_dashboard()
        assert "i2_note" in dash

    def test_dashboard_no_reorder_suggestions(self, monitor):
        """I1 dashboard must NOT contain a reorder_suggestions section."""
        dash = monitor.get_dashboard()
        assert "reorder_suggestions" not in dash


# ------------------------------------------------------------------
# 8. Transactions and movements
# ------------------------------------------------------------------

class TestHistory:
    def test_transactions_returned(self, monitor):
        txns = monitor.get_transactions()
        assert len(txns) <= 50  # default limit
        assert len(txns) > 0

    def test_transaction_schema(self, monitor):
        txns = monitor.get_transactions(limit=5)
        required = {
            "transaction_id", "timestamp", "store_id",
            "product_id", "qty", "unit_price", "discount", "revenue"
        }
        for t in txns:
            assert not (required - set(t.keys()))

    def test_transactions_filtered_by_product(self, monitor):
        txns = monitor.get_transactions(product_id="P001")
        for t in txns:
            assert t["product_id"] == "P001"

    def test_movements_returned(self, monitor):
        movs = monitor.get_movements()
        assert len(movs) > 0

    def test_movement_schema(self, monitor):
        movs = monitor.get_movements(limit=3)
        required = {"movement_id", "product_id", "movement_type", "qty", "timestamp"}
        for m in movs:
            assert not (required - set(m.keys()))
