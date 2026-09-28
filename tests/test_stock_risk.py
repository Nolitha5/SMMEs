"""
I4 Stock Risk Agent — test suite (I4-v1)

Tests:
  Unit:
    TC-I4-01  sales velocity: normal case
    TC-I4-02  sales velocity: zero sales
    TC-I4-03  sales velocity: raises on invalid observation_days
    TC-I4-04  days of cover: normal case
    TC-I4-05  days of cover: returns None on zero velocity
    TC-I4-06  days of cover: raises on negative stock
    TC-I4-07  inventory age: known receipt date
    TC-I4-08  inventory age: returns None when receipt_date=None
    TC-I4-09  days to expiry: normal case
    TC-I4-10  days to expiry: None when shelf_life missing
    TC-I4-11  days to expiry: None when age missing
    TC-I4-12  classify_expiry_risk: HIGH (<=7 days)
    TC-I4-13  classify_expiry_risk: MEDIUM (<=14 days)
    TC-I4-14  classify_expiry_risk: None (>14 days = no risk)
    TC-I4-15  classify_expiry_risk: None when days_to_expiry=None
    TC-I4-16  classify_dead_stock: True when stock>0 and velocity=0
    TC-I4-17  classify_dead_stock: False when velocity>0
    TC-I4-18  classify_dead_stock: False when stock=0
    TC-I4-19  classify_slow_stock: MEDIUM when 30 < doc <= 60
    TC-I4-20  classify_slow_stock: None when doc <= 30
    TC-I4-21  classify_slow_stock: None when doc > 60 (excess, not slow)
    TC-I4-22  classify_slow_stock: None when doc=None
    TC-I4-23  classify_excess_stock: HIGH when doc > 60
    TC-I4-24  classify_excess_stock: None when doc <= 60
    TC-I4-25  classify_excess_stock: None when doc=None
    TC-I4-26  highest_severity: returns HIGH when mixed
    TC-I4-27  highest_severity: returns MEDIUM when no HIGH
    TC-I4-28  highest_severity: returns LOW from empty list

  StockRiskAlert model:
    TC-I4-29  to_dict contains all required fields
    TC-I4-30  to_dict rounds correctly

  Agent (integration against test data dir):
    TC-I4-31  evaluate_product: product with no snapshot returns empty
    TC-I4-32  dead stock detected when sales=0 and stock>0
    TC-I4-33  no dead stock when stock=0
    TC-I4-34  slow stock detected when doc > 30
    TC-I4-35  excess stock detected when doc > 60
    TC-I4-36  expiry HIGH when days_to_expiry <= 7
    TC-I4-37  expiry MEDIUM when days_to_expiry <= 14 and > 7
    TC-I4-38  no expiry risk when days_to_expiry > 14
    TC-I4-39  no expiry risk when shelf_life unavailable
    TC-I4-40  multiple risk types on one product
    TC-I4-41  AgentResult fields populated correctly
    TC-I4-42  AgentResult requires_approval=False
    TC-I4-43  AgentResult agent_id="I4"
    TC-I4-44  AgentResult action_type="FLAG_STOCK_RISK"
    TC-I4-45  StockRiskAlert formula_version = "I4-v1"
    TC-I4-46  get_all_alerts returns list of dicts
    TC-I4-47  get_all_alerts has "recommendation" key
    TC-I4-48  get_alerts_for_product returns None for unknown product
    TC-I4-49  get_alerts_for_product returns [] for product with no risk
    TC-I4-50  missing transaction data handled safely (no crash)
    TC-I4-51  negative/invalid qty in transactions ignored
    TC-I4-52  dead stock severity: HIGH when stock>=10
    TC-I4-53  dead stock severity: MEDIUM when stock<10

  API:
    TC-I4-54  GET /api/stock-risk returns 200
    TC-I4-55  GET /api/stock-risk response has total_alerts key
    TC-I4-56  GET /api/stock-risk/{product_id} returns 200 for known product
    TC-I4-57  GET /api/stock-risk/{product_id} returns 404 for unknown product
    TC-I4-58  GET /api/stock-risk/{product_id} returns active_risks key
    TC-I4-59  GET /api/stock-risk/{product_id} is case-insensitive

  Regression:
    TC-I4-60  I1 regression — StockMonitor still loads 20 products
    TC-I4-61  I1 regression — get_inventory_positions returns InventoryPosition objects
    TC-I4-62  I2 regression — ReorderPointAgent still produces ReorderNeed
    TC-I4-63  I2 regression — evaluate_product returns tuple
    TC-I4-64  I3 regression — SafetyStockAgent still produces SafetyStockTarget
    TC-I4-65  I3 regression — evaluate_product returns tuple
"""

import csv
import io
import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

# ── Helpers ──────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"

# ── Pure function imports ─────────────────────────────────────────────────────
from app.services.stock_risk import (
    StockRiskAgent,
    calculate_sales_velocity,
    calculate_days_of_cover,
    calculate_inventory_age,
    calculate_days_to_expiry,
    classify_expiry_risk,
    classify_dead_stock,
    classify_slow_stock,
    classify_excess_stock,
    OBSERVATION_DAYS,
    SLOW_STOCK_THRESHOLD,
    EXCESS_STOCK_THRESHOLD,
    EXPIRY_HIGH_THRESHOLD,
    EXPIRY_MEDIUM_THRESHOLD,
)
from app.models.stock_risk_alert import (
    StockRiskAlert,
    RISK_EXPIRY, RISK_SLOW, RISK_DEAD, RISK_EXCESS,
    SEV_HIGH, SEV_MEDIUM, SEV_LOW,
    highest_severity, FORMULA_VERSION,
)

# ── Fixture: isolated data dir with minimal CSV files ─────────────────────────

def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _make_data_dir(
    tmp_path: Path,
    products=None,
    snapshots=None,
    transactions=None,
    movements=None,
) -> Path:
    """Create a minimal data directory for isolated agent tests."""
    if products is None:
        products = [
            {
                "product_id": "X001", "sku": "S1", "name": "TestProduct",
                "category": "Staples", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "30", "active": "True",
            }
        ]
    if snapshots is None:
        snapshots = [
            {
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001",
                "product_id": "X001",
                "stock_on_hand": "20",
                "reserved": "0",
                "damaged": "0",
                "in_transit": "0",
            }
        ]
    if transactions is None:
        transactions = []
    if movements is None:
        movements = []

    _write_csv(
        tmp_path / "products.csv",
        products,
        ["product_id", "sku", "name", "category", "unit_cost",
         "sell_price", "margin_floor", "shelf_life_days", "active"],
    )
    _write_csv(
        tmp_path / "inventory_snapshots.csv",
        snapshots,
        ["timestamp", "store_id", "product_id",
         "stock_on_hand", "reserved", "damaged", "in_transit"],
    )
    _write_csv(
        tmp_path / "transactions.csv",
        transactions,
        ["transaction_id", "timestamp", "store_id",
         "product_id", "qty", "unit_price", "discount"],
    )
    _write_csv(
        tmp_path / "inventory_movements.csv",
        movements,
        ["movement_id", "product_id", "type", "qty", "timestamp", "reference"],
    )
    return tmp_path


@pytest.fixture()
def empty_agent(tmp_path):
    """Agent with one product, zero sales, no movements."""
    d = _make_data_dir(tmp_path)
    return StockRiskAgent(data_dir=d)


@pytest.fixture()
def real_agent():
    """Agent against the real project data directory."""
    return StockRiskAgent(data_dir=DATA_DIR)


# ── FastAPI test client ───────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


# =============================================================================
# TC-I4-01 to TC-I4-03  Sales Velocity
# =============================================================================

class TestCalculateSalesVelocity:
    def test_normal_case(self):
        """TC-I4-01: 60 units in 30 days = 2.0 units/day."""
        assert calculate_sales_velocity(60, 30) == 2.0

    def test_zero_sales(self):
        """TC-I4-02: zero sales returns 0.0 (not None)."""
        assert calculate_sales_velocity(0, 30) == 0.0

    def test_invalid_observation_days(self):
        """TC-I4-03: non-positive observation_days raises ValueError."""
        with pytest.raises(ValueError):
            calculate_sales_velocity(60, 0)


# =============================================================================
# TC-I4-04 to TC-I4-06  Days of Cover
# =============================================================================

class TestCalculateDaysOfCover:
    def test_normal_case(self):
        """TC-I4-04: 40 units at 2 units/day = 20 days cover."""
        assert calculate_days_of_cover(40, 2.0) == 20.0

    def test_zero_velocity_returns_none(self):
        """TC-I4-05: zero velocity returns None (dead stock)."""
        assert calculate_days_of_cover(20, 0.0) is None

    def test_negative_stock_raises(self):
        """TC-I4-06: negative available_stock raises ValueError."""
        with pytest.raises(ValueError):
            calculate_days_of_cover(-1, 2.0)


# =============================================================================
# TC-I4-07 to TC-I4-08  Inventory Age
# =============================================================================

class TestCalculateInventoryAge:
    def test_known_receipt_date(self):
        """TC-I4-07: age is difference in days."""
        receipt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        ref     = datetime(2026, 9, 11, tzinfo=timezone.utc)
        age = calculate_inventory_age(receipt, ref)
        assert age == pytest.approx(10.0, abs=0.01)

    def test_none_when_no_receipt(self):
        """TC-I4-08: None when receipt_date is None."""
        assert calculate_inventory_age(None) is None


# =============================================================================
# TC-I4-09 to TC-I4-11  Days to Expiry
# =============================================================================

class TestCalculateDaysToExpiry:
    def test_normal_case(self):
        """TC-I4-09: 30-day shelf life, 5 days old → 25 days remaining."""
        assert calculate_days_to_expiry(30, 5.0) == pytest.approx(25.0)

    def test_none_when_no_shelf_life(self):
        """TC-I4-10: None when shelf_life_days is None."""
        assert calculate_days_to_expiry(None, 5.0) is None

    def test_none_when_no_age(self):
        """TC-I4-11: None when inventory_age_days is None."""
        assert calculate_days_to_expiry(30, None) is None


# =============================================================================
# TC-I4-12 to TC-I4-15  Classify Expiry Risk
# =============================================================================

class TestClassifyExpiryRisk:
    def test_high_within_7_days(self):
        """TC-I4-12: days_to_expiry <= 7 → HIGH."""
        assert classify_expiry_risk(6.5) == SEV_HIGH
        assert classify_expiry_risk(0.0) == SEV_HIGH

    def test_medium_within_14_days(self):
        """TC-I4-13: 7 < days_to_expiry <= 14 → MEDIUM."""
        assert classify_expiry_risk(10.0) == SEV_MEDIUM
        assert classify_expiry_risk(14.0) == SEV_MEDIUM

    def test_no_risk_beyond_14_days(self):
        """TC-I4-14: days_to_expiry > 14 → None."""
        assert classify_expiry_risk(15.0) is None
        assert classify_expiry_risk(365.0) is None

    def test_none_when_days_to_expiry_none(self):
        """TC-I4-15: None when input is None."""
        assert classify_expiry_risk(None) is None


# =============================================================================
# TC-I4-16 to TC-I4-18  Classify Dead Stock
# =============================================================================

class TestClassifyDeadStock:
    def test_dead_stock_detected(self):
        """TC-I4-16: positive stock, zero velocity → True."""
        assert classify_dead_stock(10.0, 0.0) is True

    def test_not_dead_when_velocity_positive(self):
        """TC-I4-17: positive velocity → not dead stock."""
        assert classify_dead_stock(10.0, 0.5) is False

    def test_not_dead_when_zero_stock(self):
        """TC-I4-18: zero stock → not dead stock."""
        assert classify_dead_stock(0.0, 0.0) is False


# =============================================================================
# TC-I4-19 to TC-I4-22  Classify Slow Stock
# =============================================================================

class TestClassifySlowStock:
    def test_slow_when_doc_between_30_and_60(self):
        """TC-I4-19: 30 < doc <= 60 → MEDIUM."""
        assert classify_slow_stock(45.0) == SEV_MEDIUM
        assert classify_slow_stock(31.0) == SEV_MEDIUM

    def test_not_slow_when_doc_at_or_below_30(self):
        """TC-I4-20: doc <= 30 → None."""
        assert classify_slow_stock(30.0) is None
        assert classify_slow_stock(10.0) is None

    def test_not_slow_when_doc_above_60(self):
        """TC-I4-21: doc > 60 is EXCESS, not slow → None from this function."""
        assert classify_slow_stock(61.0) is None
        assert classify_slow_stock(100.0) is None

    def test_none_when_doc_is_none(self):
        """TC-I4-22: None input → None."""
        assert classify_slow_stock(None) is None


# =============================================================================
# TC-I4-23 to TC-I4-25  Classify Excess Stock
# =============================================================================

class TestClassifyExcessStock:
    def test_excess_when_doc_above_60(self):
        """TC-I4-23: doc > 60 → HIGH."""
        assert classify_excess_stock(61.0) == SEV_HIGH
        assert classify_excess_stock(200.0) == SEV_HIGH

    def test_not_excess_when_doc_at_or_below_60(self):
        """TC-I4-24: doc <= 60 → None."""
        assert classify_excess_stock(60.0) is None
        assert classify_excess_stock(30.0) is None

    def test_none_when_doc_is_none(self):
        """TC-I4-25: None input → None."""
        assert classify_excess_stock(None) is None


# =============================================================================
# TC-I4-26 to TC-I4-28  Highest Severity
# =============================================================================

class TestHighestSeverity:
    def test_high_wins(self):
        """TC-I4-26: HIGH wins over MEDIUM and LOW."""
        assert highest_severity([SEV_LOW, SEV_HIGH, SEV_MEDIUM]) == SEV_HIGH

    def test_medium_over_low(self):
        """TC-I4-27: MEDIUM wins over LOW."""
        assert highest_severity([SEV_LOW, SEV_MEDIUM]) == SEV_MEDIUM

    def test_empty_list_returns_low(self):
        """TC-I4-28: empty list defaults to LOW."""
        assert highest_severity([]) == SEV_LOW


# =============================================================================
# TC-I4-29 to TC-I4-30  StockRiskAlert model
# =============================================================================

class TestStockRiskAlertModel:
    def _make_alert(self, **kwargs) -> StockRiskAlert:
        defaults = dict(
            product_id="X001",
            risk_type=RISK_DEAD,
            severity=SEV_HIGH,
            available_stock=20.0,
            sales_velocity=0.0,
            days_of_cover=None,
            inventory_age_days=5.0,
            shelf_life_days=30,
            days_to_expiry=25.0,
            reason="Test reason.",
            evidence_refs=["X001"],
            confidence=0.85,
        )
        defaults.update(kwargs)
        return StockRiskAlert(**defaults)

    def test_to_dict_has_required_fields(self):
        """TC-I4-29: to_dict contains all required contract fields."""
        d = self._make_alert().to_dict()
        for key in [
            "product_id", "risk_type", "severity", "available_stock",
            "sales_velocity", "days_of_cover", "inventory_age_days",
            "shelf_life_days", "days_to_expiry", "reason", "evidence_refs",
            "confidence", "generated_at", "formula_version",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_rounding(self):
        """TC-I4-30: to_dict rounds float fields correctly."""
        alert = self._make_alert(sales_velocity=1.23456789, days_of_cover=45.123456)
        d = alert.to_dict()
        assert d["sales_velocity"] == pytest.approx(1.2346, abs=1e-3)
        assert d["days_of_cover"] == pytest.approx(45.12, abs=0.01)


# =============================================================================
# TC-I4-31 to TC-I4-53  Agent integration tests (synthetic data)
# =============================================================================

class TestAgentEvaluateProduct:
    def test_unknown_product_returns_empty(self, tmp_path):
        """TC-I4-31: product not in snapshot/products returns no alerts."""
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        alerts, results = agent.evaluate_product("ZZZZ")
        assert alerts == []
        assert results == []

    def test_dead_stock_detected(self, tmp_path):
        """TC-I4-32: zero sales, positive stock → DEAD_STOCK alert."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "20", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            transactions=[],  # no sales
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        risk_types = [a.risk_type for a in alerts]
        assert RISK_DEAD in risk_types

    def test_no_dead_stock_when_zero_inventory(self, tmp_path):
        """TC-I4-33: zero stock → no dead stock flag."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "0", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        assert not any(a.risk_type == RISK_DEAD for a in alerts)

    def test_slow_stock_detected(self, tmp_path):
        """TC-I4-34: 90 units, 1 unit/day velocity → 90 days cover → SLOW or EXCESS."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        # 30 sales over 30 days = 1/day; 90 units cover = 90 days → EXCESS
        cutoff = ref - timedelta(days=OBSERVATION_DAYS)
        txns = [
            {
                "transaction_id": f"T{i}", "timestamp": (cutoff + timedelta(days=i)).strftime("%Y-%m-%dT12:00:00"),
                "store_id": "STORE-001", "product_id": "X001",
                "qty": "1", "unit_price": "20", "discount": "0",
            }
            for i in range(1, 31)
        ]
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "45", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            transactions=txns,
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        # 45 units / 1 unit/day = 45 days cover → SLOW_STOCK (30 < 45 <= 60)
        assert any(a.risk_type == RISK_SLOW for a in alerts)

    def test_excess_stock_detected(self, tmp_path):
        """TC-I4-35: 100 units, 1/day velocity → 100 days cover → EXCESS_STOCK."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        cutoff = ref - timedelta(days=OBSERVATION_DAYS)
        txns = [
            {
                "transaction_id": f"T{i}", "timestamp": (cutoff + timedelta(days=i)).strftime("%Y-%m-%dT12:00:00"),
                "store_id": "STORE-001", "product_id": "X001",
                "qty": "1", "unit_price": "20", "discount": "0",
            }
            for i in range(1, 31)
        ]
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "100", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            transactions=txns,
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        assert any(a.risk_type == RISK_EXCESS for a in alerts)

    def test_expiry_high(self, tmp_path):
        """TC-I4-36: receipt 26 days ago, shelf_life=30 → 4 days remaining → HIGH."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        receipt_ts = (ref - timedelta(days=26)).strftime("%Y-%m-%dT08:00:00")
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "Perishable",
                "category": "Dairy", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "30", "active": "True",
            }],
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "5", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            movements=[{
                "movement_id": "M1", "product_id": "X001",
                "type": "RECEIPT", "qty": "20",
                "timestamp": receipt_ts, "reference": "PO-1",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        expiry_alerts = [a for a in alerts if a.risk_type == RISK_EXPIRY]
        assert expiry_alerts, "Expected EXPIRY_RISK alert"
        assert expiry_alerts[0].severity == SEV_HIGH

    def test_expiry_medium(self, tmp_path):
        """TC-I4-37: receipt 18 days ago, shelf_life=30 → 12 days remaining → MEDIUM."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        receipt_ts = (ref - timedelta(days=18)).strftime("%Y-%m-%dT08:00:00")
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "Perishable",
                "category": "Dairy", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "30", "active": "True",
            }],
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "5", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            movements=[{
                "movement_id": "M1", "product_id": "X001",
                "type": "RECEIPT", "qty": "20",
                "timestamp": receipt_ts, "reference": "PO-1",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        expiry_alerts = [a for a in alerts if a.risk_type == RISK_EXPIRY]
        assert expiry_alerts, "Expected EXPIRY_RISK alert"
        assert expiry_alerts[0].severity == SEV_MEDIUM

    def test_no_expiry_risk_when_plenty_of_time(self, tmp_path):
        """TC-I4-38: receipt 2 days ago, shelf_life=365 → 363 days remaining → no expiry."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        receipt_ts = (ref - timedelta(days=2)).strftime("%Y-%m-%dT08:00:00")
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "LongShelf",
                "category": "Staples", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "365", "active": "True",
            }],
            movements=[{
                "movement_id": "M1", "product_id": "X001",
                "type": "RECEIPT", "qty": "20",
                "timestamp": receipt_ts, "reference": "PO-1",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        assert not any(a.risk_type == RISK_EXPIRY for a in alerts)

    def test_no_expiry_risk_when_no_shelf_life(self, tmp_path):
        """TC-I4-39: product has no shelf_life_days → no expiry flag."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "NoShelf",
                "category": "Staples", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "", "active": "True",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        assert not any(a.risk_type == RISK_EXPIRY for a in alerts)

    def test_multiple_risks_on_one_product(self, tmp_path):
        """TC-I4-40: old stock approaching expiry with low velocity → multiple risk types."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        receipt_ts = (ref - timedelta(days=25)).strftime("%Y-%m-%dT08:00:00")
        cutoff = ref - timedelta(days=OBSERVATION_DAYS)
        # Very slow sales (0.1/day) → 90 days cover → EXCESS too
        txns = [
            {
                "transaction_id": "T1",
                "timestamp": (cutoff + timedelta(days=15)).strftime("%Y-%m-%dT12:00:00"),
                "store_id": "STORE-001", "product_id": "X001",
                "qty": "3", "unit_price": "20", "discount": "0",
            }
        ]
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "Expiry+Slow",
                "category": "Dairy", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "30", "active": "True",
            }],
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "10", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            transactions=txns,
            movements=[{
                "movement_id": "M1", "product_id": "X001",
                "type": "RECEIPT", "qty": "20",
                "timestamp": receipt_ts, "reference": "PO-1",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        risk_types = {a.risk_type for a in alerts}
        # 25 days old, 30-day shelf life → 5 days to expiry → EXPIRY HIGH
        assert RISK_EXPIRY in risk_types
        # velocity = 3/30 = 0.1/day; doc = 10/0.1 = 100 days → EXCESS
        assert RISK_EXCESS in risk_types

    def test_agent_result_fields(self, tmp_path):
        """TC-I4-41: AgentResult is populated with expected fields."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        _, results = agent.evaluate_product("X001", reference_date=ref)
        if results:
            r = results[0]
            d_dict = r.to_dict()
            assert "recommendation_id" in d_dict
            assert "agent_id" in d_dict
            assert "rationale" in d_dict

    def test_agent_result_requires_approval_false(self, tmp_path):
        """TC-I4-42: I4 AlertResult requires_approval is always False."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        _, results = agent.evaluate_product("X001", reference_date=ref)
        for r in results:
            assert r.requires_approval is False

    def test_agent_id(self, tmp_path):
        """TC-I4-43: agent_id = 'I4'."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        _, results = agent.evaluate_product("X001", reference_date=ref)
        for r in results:
            assert r.agent_id == "I4"

    def test_action_type(self, tmp_path):
        """TC-I4-44: action_type = 'FLAG_STOCK_RISK'."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        _, results = agent.evaluate_product("X001", reference_date=ref)
        for r in results:
            assert r.action_type == "FLAG_STOCK_RISK"

    def test_formula_version(self, tmp_path):
        """TC-I4-45: formula_version = 'I4-v1'."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(tmp_path)
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        for a in alerts:
            assert a.formula_version == "I4-v1"


class TestGetAllAlerts:
    def test_returns_list(self, real_agent):
        """TC-I4-46: get_all_alerts returns a list."""
        results = real_agent.get_all_alerts()
        assert isinstance(results, list)

    def test_has_recommendation_key(self, real_agent):
        """TC-I4-47: each alert dict has a 'recommendation' key."""
        results = real_agent.get_all_alerts()
        for item in results:
            assert "recommendation" in item, "Missing 'recommendation' key"


class TestGetAlertsForProduct:
    def test_unknown_product_returns_none(self, real_agent):
        """TC-I4-48: get_alerts_for_product returns None for unknown product."""
        assert real_agent.get_alerts_for_product("ZZZZZZZ") is None

    def test_known_product_with_no_risk_returns_empty_list(self, tmp_path):
        """TC-I4-49: product exists but no risk → empty list (not None)."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        cutoff = ref - timedelta(days=OBSERVATION_DAYS)
        # stock = 5, velocity = 5/day → doc = 1 day → no slow/excess/dead
        txns = [
            {
                "transaction_id": f"T{i}",
                "timestamp": (cutoff + timedelta(days=i)).strftime("%Y-%m-%dT12:00:00"),
                "store_id": "STORE-001", "product_id": "X001",
                "qty": "5", "unit_price": "20", "discount": "0",
            }
            for i in range(1, 31)
        ]
        receipt_ts = (ref - timedelta(days=2)).strftime("%Y-%m-%dT08:00:00")
        d = _make_data_dir(
            tmp_path,
            products=[{
                "product_id": "X001", "sku": "S1", "name": "Healthy",
                "category": "Staples", "unit_cost": "10", "sell_price": "20",
                "margin_floor": "2", "shelf_life_days": "365", "active": "True",
            }],
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "5", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
            transactions=txns,
            movements=[{
                "movement_id": "M1", "product_id": "X001",
                "type": "RECEIPT", "qty": "50",
                "timestamp": receipt_ts, "reference": "PO-1",
            }],
        )
        agent = StockRiskAgent(data_dir=d, observation_days=OBSERVATION_DAYS)
        result = agent.get_alerts_for_product("X001", reference_date=ref)
        assert result == []


class TestMissingDataHandling:
    def test_no_crash_on_empty_transactions(self, tmp_path):
        """TC-I4-50: missing transaction data does not crash the agent."""
        d = _make_data_dir(tmp_path, transactions=[])
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001")
        # Should not raise; may detect dead stock or no alerts
        assert isinstance(alerts, list)

    def test_invalid_qty_ignored(self, tmp_path):
        """TC-I4-51: non-numeric qty rows are skipped, no crash."""
        d = _make_data_dir(
            tmp_path,
            transactions=[
                {
                    "transaction_id": "T1",
                    "timestamp": "2026-09-10T10:00:00",
                    "store_id": "STORE-001", "product_id": "X001",
                    "qty": "not-a-number", "unit_price": "20", "discount": "0",
                }
            ],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001")
        assert isinstance(alerts, list)


class TestDeadStockSeverity:
    def test_dead_stock_high_when_stock_gte_10(self, tmp_path):
        """TC-I4-52: dead stock with >= 10 units → HIGH."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "15", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        dead = [a for a in alerts if a.risk_type == RISK_DEAD]
        assert dead and dead[0].severity == SEV_HIGH

    def test_dead_stock_medium_when_stock_lt_10(self, tmp_path):
        """TC-I4-53: dead stock with < 10 units → MEDIUM."""
        ref = datetime(2026, 9, 21, tzinfo=timezone.utc)
        d = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00",
                "store_id": "STORE-001", "product_id": "X001",
                "stock_on_hand": "5", "reserved": "0",
                "damaged": "0", "in_transit": "0",
            }],
        )
        agent = StockRiskAgent(data_dir=d)
        alerts, _ = agent.evaluate_product("X001", reference_date=ref)
        dead = [a for a in alerts if a.risk_type == RISK_DEAD]
        assert dead and dead[0].severity == SEV_MEDIUM


# =============================================================================
# TC-I4-54 to TC-I4-59  API endpoint tests
# =============================================================================

class TestApiStockRiskList:
    def test_returns_200(self, client):
        """TC-I4-54: GET /api/stock-risk returns 200."""
        r = client.get("/api/stock-risk/")
        assert r.status_code == 200

    def test_has_total_alerts_key(self, client):
        """TC-I4-55: response has 'total_alerts' key."""
        r = client.get("/api/stock-risk/")
        data = r.json()
        assert "total_alerts" in data
        assert isinstance(data["total_alerts"], int)


class TestApiStockRiskProduct:
    def test_known_product_returns_200(self, client):
        """TC-I4-56: GET /api/stock-risk/P001 returns 200."""
        r = client.get("/api/stock-risk/P001")
        assert r.status_code == 200

    def test_unknown_product_returns_404(self, client):
        """TC-I4-57: GET /api/stock-risk/UNKNOWN returns 404."""
        r = client.get("/api/stock-risk/UNKNOWN")
        assert r.status_code == 404

    def test_has_active_risks_key(self, client):
        """TC-I4-58: response has 'active_risks' key."""
        r = client.get("/api/stock-risk/P001")
        data = r.json()
        assert "active_risks" in data

    def test_case_insensitive(self, client):
        """TC-I4-59: product_id lookup is case-insensitive."""
        r_lower = client.get("/api/stock-risk/p001")
        r_upper = client.get("/api/stock-risk/P001")
        assert r_lower.status_code == 200
        assert r_upper.status_code == 200


# =============================================================================
# TC-I4-60 to TC-I4-65  Regression
# =============================================================================

class TestI1Regression:
    def test_stock_monitor_loads_products(self):
        """TC-I4-60: I1 StockMonitor still loads 20 products."""
        from app.services.stock_monitor import StockMonitor
        monitor = StockMonitor(data_dir=DATA_DIR)
        assert len(monitor._products) == 20

    def test_stock_monitor_returns_inventory_positions(self):
        """TC-I4-61: I1 get_inventory_positions returns InventoryPosition objects."""
        from app.services.stock_monitor import StockMonitor
        from app.models.inventory_position import InventoryPosition
        monitor = StockMonitor(data_dir=DATA_DIR)
        positions = monitor.get_inventory_positions()
        assert len(positions) > 0
        for pos in positions:
            assert isinstance(pos, InventoryPosition)


class TestI2Regression:
    def test_reorder_agent_produces_reorder_need(self):
        """TC-I4-62: I2 ReorderPointAgent still produces ReorderNeed."""
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor
        from app.models.reorder_need import ReorderNeed
        monitor = StockMonitor(data_dir=DATA_DIR)
        agent   = ReorderPointAgent(data_dir=DATA_DIR)
        positions = monitor.get_inventory_positions()
        assert positions
        pos = positions[0]
        result = agent.evaluate_product(pos)
        assert result is not None
        assert isinstance(result, ReorderNeed)

    def test_reorder_evaluate_product_returns_reorder_need(self):
        """TC-I4-63: I2 evaluate_product returns a ReorderNeed."""
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor
        from app.models.reorder_need import ReorderNeed as RN
        monitor = StockMonitor(data_dir=DATA_DIR)
        agent   = ReorderPointAgent(data_dir=DATA_DIR)
        positions = monitor.get_inventory_positions()
        result = agent.evaluate_product(positions[0])
        assert isinstance(result, RN)


class TestI3Regression:
    def test_safety_stock_agent_produces_target(self):
        """TC-I4-64: I3 SafetyStockAgent still produces SafetyStockTarget."""
        from app.services.safety_stock import SafetyStockAgent
        from app.models.safety_stock_target import SafetyStockTarget
        agent = SafetyStockAgent(data_dir=DATA_DIR)
        result = agent.evaluate_product("P001", "Bakery")
        assert result is not None
        target, ar = result
        assert isinstance(target, SafetyStockTarget)

    def test_safety_stock_evaluate_returns_tuple(self):
        """TC-I4-65: I3 evaluate_product returns a 2-tuple."""
        from app.services.safety_stock import SafetyStockAgent
        agent = SafetyStockAgent(data_dir=DATA_DIR)
        result = agent.evaluate_product("P001", "Bakery")
        assert isinstance(result, tuple)
        assert len(result) == 2
