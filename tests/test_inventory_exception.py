"""
I5 Inventory Exception Agent — Test Suite
TC-I5-01 through TC-I5-60

Covers:
  - All five exception detection functions (pure functions)
  - InventoryException model
  - AgentResult integration
  - InventoryExceptionAgent with synthetic CSV data (tmp_path fixtures)
  - API endpoints
  - Regression: I1, I2, I3, I4
  - R5 future hook / default behaviour
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

# ── Paths for integration tests ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# ── Helpers ────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _make_data_dir(
    tmp_path: Path,
    products: list[dict] | None = None,
    snapshots: list[dict] | None = None,
    movements: list[dict] | None = None,
    transactions: list[dict] | None = None,
) -> Path:
    """Create a minimal data directory for unit tests."""
    data = tmp_path / "data"
    data.mkdir()

    if products is None:
        products = [
            {"product_id": "P001", "sku": "SKU001", "name": "Bread",
             "category": "Bakery", "unit_cost": "5.00", "sell_price": "10.00",
             "margin_floor": "0.20", "shelf_life_days": "3", "active": "true"},
        ]
    _write_csv(data / "products.csv", products,
               ["product_id","sku","name","category","unit_cost","sell_price",
                "margin_floor","shelf_life_days","active"])

    if snapshots is None:
        snapshots = [
            {"timestamp": "2026-08-11T17:00:00", "store_id": "STORE-001",
             "product_id": "P001", "stock_on_hand": "10",
             "reserved": "0", "damaged": "0", "in_transit": "0"},
        ]
    _write_csv(data / "inventory_snapshots.csv", snapshots,
               ["timestamp","store_id","product_id","stock_on_hand",
                "reserved","damaged","in_transit"])

    if movements is None:
        movements = [
            {"movement_id": "M0001", "product_id": "P001", "type": "RECEIPT",
             "qty": "10", "timestamp": "2026-08-11T08:00:00", "reference": "PO-1"},
        ]
    _write_csv(data / "inventory_movements.csv", movements,
               ["movement_id","product_id","type","qty","timestamp","reference"])

    if transactions is None:
        transactions = []
    _write_csv(data / "transactions.csv", transactions,
               ["transaction_id","timestamp","store_id","product_id","qty",
                "unit_price","discount"])

    return data


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-01 to TC-I5-10 — Pure function: check_negative_stock
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckNegativeStock:
    from app.services.inventory_exception import check_negative_stock

    def test_negative_stock_returns_exception(self):
        """TC-I5-01: available < 0 → HIGH exception."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 0.0, 0.0, 1.0, "2026-09-09T17:00:00")
        assert exc is not None
        assert exc.exception_type == "NEGATIVE_STOCK"
        assert exc.severity == "HIGH"

    def test_zero_stock_no_exception(self):
        """TC-I5-02: available = 0 → no exception."""
        from app.services.inventory_exception import check_negative_stock
        assert check_negative_stock("P001", 0.0, 0.0, 0.0, "2026-09-09T17:00:00") is None

    def test_positive_stock_no_exception(self):
        """TC-I5-03: available > 0 → no exception."""
        from app.services.inventory_exception import check_negative_stock
        assert check_negative_stock("P001", 10.0, 1.0, 1.0, "2026-09-09T17:00:00") is None

    def test_negative_from_reservation(self):
        """TC-I5-04: stock_on_hand=2, reserved=2, damaged=1 → available=-1 → exception."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P002", 2.0, 2.0, 1.0, "2026-09-09T17:00:00")
        assert exc is not None
        assert exc.actual_value == -1.0

    def test_exception_status_open(self):
        """TC-I5-05: returned exception has status OPEN."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 0.0, 0.0, 5.0, "2026-09-09T17:00:00")
        assert exc.status == "OPEN"

    def test_exception_has_evidence_refs(self):
        """TC-I5-06: evidence_refs contains the snapshot reference."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 0.0, 0.0, 2.0, "2026-09-09T17:00:00")
        assert any("inventory_snapshots.csv" in ref for ref in exc.evidence_refs)

    def test_exception_id_format(self):
        """TC-I5-07: exception_id starts with 'I5-'."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 0.0, 0.0, 1.0, "2026-09-09T17:00:00")
        assert exc.exception_id.startswith("I5-")

    def test_formula_version(self):
        """TC-I5-08: formula_version is I5-v1."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 0.0, 0.0, 1.0, "2026-09-09T17:00:00")
        assert exc.formula_version == "I5-v1"

    def test_affected_quantity_negative(self):
        """TC-I5-09: affected_quantity is the negative available stock value."""
        from app.services.inventory_exception import check_negative_stock
        exc = check_negative_stock("P001", 1.0, 1.0, 3.0, "2026-09-09T17:00:00")
        # available = 1 - 1 - 3 = -3
        assert exc.affected_quantity == -3.0

    def test_real_data_p001_negative(self):
        """TC-I5-10: Real data — P001 latest snapshot has available = -1."""
        from app.services.inventory_exception import check_negative_stock
        # P001 latest: stock_on_hand=0, reserved=0, damaged=1 → -1
        exc = check_negative_stock("P001", 0.0, 0.0, 1.0, "2026-09-09T17:00:00")
        assert exc is not None
        assert exc.severity == "HIGH"


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-11 to TC-I5-20 — Pure function: check_large_adjustment
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckLargeAdjustment:

    def test_small_adjustment_no_flag(self):
        """TC-I5-11: |qty| < 10 → no exception."""
        from app.services.inventory_exception import check_large_adjustment
        assert check_large_adjustment("P001", "M001", "ADJUSTMENT", -5, "2026-09-01", 50) is None

    def test_medium_threshold(self):
        """TC-I5-12: |qty| == 10 → MEDIUM."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M001", "ADJUSTMENT", -10, "2026-09-01", 50)
        assert exc is not None
        assert exc.severity == "MEDIUM"

    def test_high_threshold(self):
        """TC-I5-13: |qty| == 20 → HIGH."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M001", "ADJUSTMENT", -20, "2026-09-01", 50)
        assert exc is not None
        assert exc.severity == "HIGH"

    def test_damage_type_flagged(self):
        """TC-I5-14: DAMAGE movements are also checked."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M001", "DAMAGE", -15, "2026-09-01", 50)
        assert exc is not None

    def test_receipt_not_flagged(self):
        """TC-I5-15: RECEIPT movements are never large-adjustment exceptions."""
        from app.services.inventory_exception import check_large_adjustment
        assert check_large_adjustment("P001", "M001", "RECEIPT", 100, "2026-09-01", 50) is None

    def test_sale_not_flagged(self):
        """TC-I5-16: SALE movements are not large-adjustment exceptions (Rule 5 handles suspect sales)."""
        from app.services.inventory_exception import check_large_adjustment
        assert check_large_adjustment("P001", "M001", "SALE", 200, "2026-09-01", 50) is None

    def test_exception_type_correct(self):
        """TC-I5-17: exception_type is LARGE_STOCK_ADJUSTMENT."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M001", "ADJUSTMENT", -25, "2026-09-01", 50)
        assert exc.exception_type == "LARGE_STOCK_ADJUSTMENT"

    def test_evidence_refs_contain_movement_id(self):
        """TC-I5-18: evidence_refs reference the movement."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M999", "ADJUSTMENT", -15, "2026-09-01", 50)
        assert any("M999" in ref for ref in exc.evidence_refs)

    def test_real_m025_p011_flagged(self):
        """TC-I5-19: Real data M0025 P011 ADJUSTMENT -25 → HIGH."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P011", "M0025", "ADJUSTMENT", -25, "2026-09-04T16:00:00", 9)
        assert exc is not None
        assert exc.severity == "HIGH"

    def test_status_open(self):
        """TC-I5-20: large adjustment exception has status OPEN."""
        from app.services.inventory_exception import check_large_adjustment
        exc = check_large_adjustment("P001", "M001", "ADJUSTMENT", -25, "2026-09-01", 50)
        assert exc.status == "OPEN"


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-21 to TC-I5-28 — Pure function: check_movement_snapshot_mismatch
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckMovementSnapshotMismatch:

    def test_no_mismatch_within_tolerance(self):
        """TC-I5-21: discrepancy <= 2 → no exception."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        # opening=10, net=+5, expected=15, actual=14 → gap=1 ≤ 2
        assert check_movement_snapshot_mismatch(
            "P001", 10, 14, "T1", "T2", 5.0, []) is None

    def test_medium_mismatch(self):
        """TC-I5-22: discrepancy > 5 → MEDIUM."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        # opening=10, net=0, expected=10, actual=3 → gap=7
        exc = check_movement_snapshot_mismatch("P001", 10, 3, "T1", "T2", 0.0, [])
        assert exc is not None
        assert exc.severity == "MEDIUM"

    def test_high_mismatch(self):
        """TC-I5-23: discrepancy > 20 → HIGH."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        # opening=25, net=-200, expected=-175, actual=21 → gap=196
        exc = check_movement_snapshot_mismatch("P005", 25, 21, "T1", "T2", -200.0, ["M0023"])
        assert exc is not None
        assert exc.severity == "HIGH"

    def test_exception_type(self):
        """TC-I5-24: exception_type is MOVEMENT_SNAPSHOT_MISMATCH."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        exc = check_movement_snapshot_mismatch("P001", 10, 3, "T1", "T2", 0.0, [])
        assert exc.exception_type == "MOVEMENT_SNAPSHOT_MISMATCH"

    def test_expected_and_actual_values(self):
        """TC-I5-25: expected_value and actual_value are correctly populated."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        exc = check_movement_snapshot_mismatch("P001", 10, 3, "T1", "T2", 0.0, [])
        assert exc.expected_value == 10.0
        assert exc.actual_value == 3.0

    def test_movement_ids_in_evidence(self):
        """TC-I5-26: movement IDs appear in evidence_refs."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        exc = check_movement_snapshot_mismatch(
            "P001", 10, 0, "T1", "T2", 0.0, ["M0001","M0002"])
        assert any("M0001" in r for r in exc.evidence_refs)

    def test_positive_net_no_mismatch(self):
        """TC-I5-27: opening=10, net=+5, actual=15 → perfectly reconciled."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        assert check_movement_snapshot_mismatch(
            "P001", 10, 15, "T1", "T2", 5.0, []) is None

    def test_affected_quantity_is_discrepancy(self):
        """TC-I5-28: affected_quantity equals the absolute discrepancy."""
        from app.services.inventory_exception import check_movement_snapshot_mismatch
        exc = check_movement_snapshot_mismatch("P001", 10, 3, "T1", "T2", 0.0, [])
        assert exc.affected_quantity == 7.0


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-29 to TC-I5-34 — Pure function: check_receipt_stock_mismatch
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckReceiptStockMismatch:

    def test_no_mismatch_within_tolerance(self):
        """TC-I5-29: receipt of 10, stock went from 5 to 13, sales=2 → expected_min=13, actual=13 → ok."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        # expected_min = 5 + 10 - 2 - 2(tolerance) = 11; actual=13 >= 11
        assert check_receipt_stock_mismatch(
            "P001", "M001", 10, 5, 13, "T1", "T2", 2) is None

    def test_mismatch_flagged(self):
        """TC-I5-30: receipt of 60, stock went 5→10, sales=0 → expected_min=63, actual=10 → mismatch."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        exc = check_receipt_stock_mismatch(
            "P001", "M001", 60, 5, 10, "T1", "T2", 0)
        assert exc is not None
        assert exc.exception_type == "RECEIPT_STOCK_MISMATCH"

    def test_r5_mode_match(self):
        """TC-I5-31: R5 qty matches movement qty → no exception."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        assert check_receipt_stock_mismatch(
            "P001", "M001", 50, 0, 50, "T1", "T2", 0,
            r5_delivery_qty=50) is None

    def test_r5_mode_mismatch(self):
        """TC-I5-32: R5 qty differs by 25 → exception."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        exc = check_receipt_stock_mismatch(
            "P001", "M001", 50, 0, 50, "T1", "T2", 0,
            r5_delivery_qty=25)
        assert exc is not None
        assert exc.severity == "HIGH"

    def test_r5_note_in_reason_when_no_r5(self):
        """TC-I5-33: When r5_delivery_qty=None, reason notes MVP limitation."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        exc = check_receipt_stock_mismatch(
            "P001", "M001", 60, 5, 10, "T1", "T2", 0)
        assert "R5" in exc.reason or "MVP" in exc.reason

    def test_status_open(self):
        """TC-I5-34: receipt mismatch exception has status OPEN."""
        from app.services.inventory_exception import check_receipt_stock_mismatch
        exc = check_receipt_stock_mismatch(
            "P001", "M001", 60, 5, 10, "T1", "T2", 0)
        assert exc.status == "OPEN"


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-35 to TC-I5-42 — Pure function: check_duplicate_movements
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckDuplicateMovements:

    def _make_move(self, mid, pid, mtype, qty, ts):
        return {"movement_id": mid, "product_id": pid,
                "type": mtype, "qty": str(qty), "timestamp": ts}

    def test_no_duplicates_empty_result(self):
        """TC-I5-35: unique movements → no exceptions."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [
            self._make_move("M001", "P001", "RECEIPT", 10, "2026-08-11T08:00:00"),
            self._make_move("M002", "P001", "SALE", 3, "2026-08-12T12:00:00"),
        ]
        assert check_duplicate_movements("P001", moves) == []

    def test_duplicate_id_flagged(self):
        """TC-I5-36: same movement_id twice → DUPLICATE_SUSPICIOUS_MOVEMENT."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [
            self._make_move("M001", "P001", "RECEIPT", 10, "2026-08-11T08:00:00"),
            self._make_move("M001", "P001", "RECEIPT", 10, "2026-08-11T08:00:00"),
        ]
        excs = check_duplicate_movements("P001", moves)
        assert any(e.exception_type == "DUPLICATE_SUSPICIOUS_MOVEMENT" for e in excs)

    def test_impossible_receipt_zero_qty(self):
        """TC-I5-37: RECEIPT with qty=0 → HIGH exception."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [self._make_move("M001", "P001", "RECEIPT", 0, "2026-08-11T08:00:00")]
        excs = check_duplicate_movements("P001", moves)
        assert any(e.severity == "HIGH" for e in excs)

    def test_impossible_receipt_negative_qty(self):
        """TC-I5-38: RECEIPT with qty=-5 → HIGH exception."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [self._make_move("M001", "P001", "RECEIPT", -5, "2026-08-11T08:00:00")]
        excs = check_duplicate_movements("P001", moves)
        assert any(e.severity == "HIGH" for e in excs)

    def test_sale_zero_qty_flagged(self):
        """TC-I5-39: SALE with qty=0 → MEDIUM exception."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [self._make_move("M001", "P001", "SALE", 0, "2026-08-11T08:00:00")]
        excs = check_duplicate_movements("P001", moves)
        assert any(e.severity == "MEDIUM" for e in excs)

    def test_identical_record_flagged(self):
        """TC-I5-40: two records with same product/type/qty/timestamp → flagged."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [
            self._make_move("M001", "P001", "SALE", 5, "2026-08-12T12:00:00"),
            self._make_move("M002", "P001", "SALE", 5, "2026-08-12T12:00:00"),
        ]
        excs = check_duplicate_movements("P001", moves)
        assert len(excs) >= 1

    def test_valid_sale_positive_qty_no_flag(self):
        """TC-I5-41: SALE with positive qty → no impossible-value exception."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [self._make_move("M001", "P001", "SALE", 5, "2026-08-12T12:00:00")]
        excs = check_duplicate_movements("P001", moves)
        assert excs == []

    def test_exception_type_correct(self):
        """TC-I5-42: all returned exceptions have correct exception_type."""
        from app.services.inventory_exception import check_duplicate_movements
        moves = [self._make_move("M001", "P001", "RECEIPT", 0, "2026-08-11")]
        excs = check_duplicate_movements("P001", moves)
        for e in excs:
            assert e.exception_type == "DUPLICATE_SUSPICIOUS_MOVEMENT"


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-43 to TC-I5-47 — InventoryException model
# ─────────────────────────────────────────────────────────────────────────────

class TestInventoryExceptionModel:

    def _make_exc(self, **kwargs):
        from app.models.inventory_exception import InventoryException
        defaults = dict(
            exception_id="I5-ABC123",
            product_id="P001",
            exception_type="NEGATIVE_STOCK",
            severity="HIGH",
            status="OPEN",
            message="Test message.",
            reason="Test reason.",
            evidence_refs=["inventory_snapshots.csv:P001:2026-09-09T17:00:00"],
            affected_quantity=-1.0,
            expected_value=0.0,
            actual_value=-1.0,
        )
        defaults.update(kwargs)
        return InventoryException(**defaults)

    def test_to_dict_contains_required_keys(self):
        """TC-I5-43: to_dict() includes all required fields."""
        exc = self._make_exc()
        d = exc.to_dict()
        for key in ["exception_id","product_id","exception_type","severity",
                    "status","message","reason","evidence_refs",
                    "affected_quantity","expected_value","actual_value",
                    "generated_at","formula_version","confidence"]:
            assert key in d, f"Missing key: {key}"

    def test_formula_version(self):
        """TC-I5-44: formula_version defaults to I5-v1."""
        exc = self._make_exc()
        assert exc.formula_version == "I5-v1"

    def test_status_open(self):
        """TC-I5-45: default status is OPEN."""
        exc = self._make_exc()
        assert exc.status == "OPEN"

    def test_confidence_default(self):
        """TC-I5-46: confidence defaults to 1.0."""
        exc = self._make_exc()
        assert exc.confidence == 1.0

    def test_generated_at_is_datetime(self):
        """TC-I5-47: generated_at is a datetime object."""
        exc = self._make_exc()
        assert isinstance(exc.generated_at, datetime)


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-48 to TC-I5-52 — AgentResult integration
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentResultIntegration:

    def _get_agent_result(self, tmp_path):
        from app.services.inventory_exception import InventoryExceptionAgent
        # Create negative stock scenario
        data = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00", "store_id": "STORE-001",
                "product_id": "P001", "stock_on_hand": "0",
                "reserved": "0", "damaged": "1", "in_transit": "0",
            }],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.evaluate_product("P001")
        assert result is not None
        excs, ars = result
        assert len(ars) >= 1
        return ars[0]

    def test_agent_id_is_i5(self, tmp_path):
        """TC-I5-48: AgentResult.agent_id == 'I5'."""
        ar = self._get_agent_result(tmp_path)
        assert ar.agent_id == "I5"

    def test_action_type(self, tmp_path):
        """TC-I5-49: action_type == 'FLAG_INVENTORY_EXCEPTION'."""
        ar = self._get_agent_result(tmp_path)
        assert ar.action_type == "FLAG_INVENTORY_EXCEPTION"

    def test_entity_type_product(self, tmp_path):
        """TC-I5-50: entity_type == 'PRODUCT'."""
        ar = self._get_agent_result(tmp_path)
        assert ar.entity_type == "PRODUCT"

    def test_requires_approval_false(self, tmp_path):
        """TC-I5-51: requires_approval is False (I5 only detects, does not act)."""
        ar = self._get_agent_result(tmp_path)
        assert ar.requires_approval is False

    def test_risk_level_matches_severity(self, tmp_path):
        """TC-I5-52: AgentResult.risk_level matches InventoryException.severity."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00", "store_id": "STORE-001",
                "product_id": "P001", "stock_on_hand": "0",
                "reserved": "0", "damaged": "1", "in_transit": "0",
            }],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        excs, ars = agent.evaluate_product("P001")
        neg_exc = next(e for e in excs if e.exception_type == "NEGATIVE_STOCK")
        neg_ar  = next(a for a in ars if "NEGATIVE_STOCK" in a.action)
        assert neg_ar.risk_level == neg_exc.severity


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-53 to TC-I5-57 — InventoryExceptionAgent (integration, tmp_path)
# ─────────────────────────────────────────────────────────────────────────────

class TestInventoryExceptionAgent:

    def test_unknown_product_returns_none(self, tmp_path):
        """TC-I5-53: evaluate_product for unknown product_id → None."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(tmp_path)
        agent = InventoryExceptionAgent(data_dir=data)
        assert agent.evaluate_product("ZZZZ") is None

    def test_healthy_product_no_exceptions(self, tmp_path):
        """TC-I5-54: clean data → ([], [])."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-08-11T17:00:00", "store_id": "STORE-001",
                "product_id": "P001", "stock_on_hand": "10",
                "reserved": "0", "damaged": "0", "in_transit": "0",
            }],
            movements=[{
                "movement_id": "M0001", "product_id": "P001",
                "type": "RECEIPT", "qty": "10",
                "timestamp": "2026-08-11T08:00:00", "reference": "PO-1",
            }],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.evaluate_product("P001")
        assert result is not None
        excs, ars = result
        assert all(e.exception_type != "NEGATIVE_STOCK" for e in excs)

    def test_negative_stock_detected_by_agent(self, tmp_path):
        """TC-I5-55: agent detects NEGATIVE_STOCK from snapshot."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-09-09T17:00:00", "store_id": "STORE-001",
                "product_id": "P001", "stock_on_hand": "0",
                "reserved": "0", "damaged": "2", "in_transit": "0",
            }],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        excs, _ = agent.evaluate_product("P001")
        neg = [e for e in excs if e.exception_type == "NEGATIVE_STOCK"]
        assert len(neg) == 1
        assert neg[0].severity == "HIGH"

    def test_large_adjustment_detected_by_agent(self, tmp_path):
        """TC-I5-56: agent detects LARGE_STOCK_ADJUSTMENT from movements."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(
            tmp_path,
            movements=[
                {"movement_id": "M0001", "product_id": "P001",
                 "type": "RECEIPT", "qty": "10",
                 "timestamp": "2026-08-11T08:00:00", "reference": "PO-1"},
                {"movement_id": "M0002", "product_id": "P001",
                 "type": "ADJUSTMENT", "qty": "-25",
                 "timestamp": "2026-09-04T16:00:00", "reference": "ADJ-X"},
            ],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        excs, _ = agent.evaluate_product("P001")
        adj = [e for e in excs if e.exception_type == "LARGE_STOCK_ADJUSTMENT"]
        assert len(adj) >= 1

    def test_get_all_exceptions_returns_list(self, tmp_path):
        """TC-I5-57: get_all_exceptions() returns a list of dicts."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(tmp_path)
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.get_all_exceptions()
        assert isinstance(result, list)

    def test_get_exceptions_for_unknown_product_returns_none(self, tmp_path):
        """TC-I5-58: get_exceptions_for_product for unknown → None."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(tmp_path)
        agent = InventoryExceptionAgent(data_dir=data)
        assert agent.get_exceptions_for_product("ZZZZ") is None

    def test_get_exceptions_for_product_with_no_exception_returns_list(self, tmp_path):
        """TC-I5-59: known product with no exceptions → empty list (not None)."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(
            tmp_path,
            snapshots=[{
                "timestamp": "2026-08-11T17:00:00", "store_id": "STORE-001",
                "product_id": "P001", "stock_on_hand": "10",
                "reserved": "0", "damaged": "0", "in_transit": "0",
            }],
            movements=[{
                "movement_id": "M0001", "product_id": "P001",
                "type": "RECEIPT", "qty": "10",
                "timestamp": "2026-08-11T08:00:00", "reference": "PO-1",
            }],
        )
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.get_exceptions_for_product("P001")
        assert isinstance(result, list)

    def test_r5_hook_default_none(self, tmp_path):
        """TC-I5-60: procurement_deliveries defaults to None — no crash, MVP partial check runs."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(tmp_path)
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.evaluate_product("P001", procurement_deliveries=None)
        assert result is not None  # returns tuple, not None

    def test_r5_hook_empty_list(self, tmp_path):
        """TC-I5-61: empty procurement_deliveries list → no crash."""
        from app.services.inventory_exception import InventoryExceptionAgent
        data = _make_data_dir(tmp_path)
        agent = InventoryExceptionAgent(data_dir=data)
        result = agent.evaluate_product("P001", procurement_deliveries=[])
        assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-62 to TC-I5-65 — Real data integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRealDataIntegration:

    def _agent(self):
        from app.services.inventory_exception import InventoryExceptionAgent
        return InventoryExceptionAgent(data_dir=DATA_DIR)

    def test_p001_negative_stock_detected(self):
        """TC-I5-62: Real data P001 has available_stock=-1 → NEGATIVE_STOCK."""
        agent = self._agent()
        excs, _ = agent.evaluate_product("P001")
        neg = [e for e in excs if e.exception_type == "NEGATIVE_STOCK"]
        assert len(neg) == 1
        assert neg[0].severity == "HIGH"

    def test_p011_large_adjustment_detected(self):
        """TC-I5-63: Real data M0025 P011 ADJUSTMENT -25 → LARGE_STOCK_ADJUSTMENT."""
        agent = self._agent()
        excs, _ = agent.evaluate_product("P011")
        adj = [e for e in excs if e.exception_type == "LARGE_STOCK_ADJUSTMENT"]
        assert len(adj) >= 1

    def test_p005_mismatch_detected(self):
        """TC-I5-64: Real data P005 M0023 SALE 200 causes snapshot mismatch."""
        agent = self._agent()
        excs, _ = agent.evaluate_product("P005")
        mm = [e for e in excs if e.exception_type == "MOVEMENT_SNAPSHOT_MISMATCH"]
        assert len(mm) >= 1

    def test_get_all_exceptions_not_empty(self):
        """TC-I5-65: Real data has at least one exception."""
        agent = self._agent()
        all_excs = agent.get_all_exceptions()
        assert len(all_excs) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-66 to TC-I5-71 — API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    from app.main import app
    with TestClient(app) as c:
        yield c


class TestApiInventoryExceptions:

    def test_list_endpoint_status_200(self, api_client):
        """TC-I5-66: GET /api/inventory-exceptions → 200."""
        r = api_client.get("/api/inventory-exceptions")
        assert r.status_code == 200

    def test_list_endpoint_schema(self, api_client):
        """TC-I5-67: response contains 'total_exceptions' and 'exceptions' list."""
        r = api_client.get("/api/inventory-exceptions")
        data = r.json()
        assert "total_exceptions" in data
        assert "exceptions" in data
        assert isinstance(data["exceptions"], list)

    def test_list_has_exceptions(self, api_client):
        """TC-I5-68: real data returns at least one exception."""
        r = api_client.get("/api/inventory-exceptions")
        assert r.json()["total_exceptions"] >= 1

    def test_product_endpoint_known_product(self, api_client):
        """TC-I5-69: GET /api/inventory-exceptions/P001 → 200."""
        r = api_client.get("/api/inventory-exceptions/P001")
        assert r.status_code == 200

    def test_product_endpoint_schema(self, api_client):
        """TC-I5-70: single-product response has correct keys."""
        r = api_client.get("/api/inventory-exceptions/P001")
        data = r.json()
        assert "product_id" in data
        assert "active_exceptions" in data
        assert "exceptions" in data

    def test_product_endpoint_unknown_404(self, api_client):
        """TC-I5-71: GET /api/inventory-exceptions/ZZZZ → 404."""
        r = api_client.get("/api/inventory-exceptions/ZZZZ")
        assert r.status_code == 404

    def test_product_endpoint_p001_has_exception(self, api_client):
        """TC-I5-72: P001 has at least one active exception (NEGATIVE_STOCK)."""
        r = api_client.get("/api/inventory-exceptions/P001")
        data = r.json()
        assert data["active_exceptions"] >= 1
        types = [e["exception_type"] for e in data["exceptions"]]
        assert "NEGATIVE_STOCK" in types

    def test_exception_dict_contains_agent_result(self, api_client):
        """TC-I5-73: each exception dict contains 'agent_result' sub-dict."""
        r = api_client.get("/api/inventory-exceptions/P001")
        data = r.json()
        for exc in data["exceptions"]:
            assert "agent_result" in exc
            assert exc["agent_result"]["agent_id"] == "I5"


# ─────────────────────────────────────────────────────────────────────────────
# TC-I5-74 to TC-I5-77 — Regression: I1, I2, I3, I4
# ─────────────────────────────────────────────────────────────────────────────

class TestI1Regression:

    def test_stock_monitor_loads(self):
        """TC-I5-74: I1 StockMonitor still loads without error."""
        from app.services.stock_monitor import StockMonitor
        monitor = StockMonitor(data_dir=DATA_DIR)
        assert len(monitor._products) > 0

    def test_inventory_positions_non_empty(self):
        """TC-I5-75: I1 get_inventory_positions() still returns positions."""
        from app.services.stock_monitor import StockMonitor
        monitor = StockMonitor(data_dir=DATA_DIR)
        positions = monitor.get_inventory_positions()
        assert len(positions) > 0


class TestI2Regression:

    def test_reorder_agent_loads(self):
        """TC-I5-76: I2 ReorderPointAgent still loads without error."""
        from app.services.reorder_point import ReorderPointAgent
        agent = ReorderPointAgent(data_dir=DATA_DIR)
        assert len(agent._suppliers) > 0

    def test_reorder_agent_evaluates(self):
        """TC-I5-77: I2 evaluate_product still returns a ReorderNeed."""
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor
        from app.models.reorder_need import ReorderNeed
        monitor = StockMonitor(data_dir=DATA_DIR)
        agent = ReorderPointAgent(data_dir=DATA_DIR)
        pos = monitor.get_inventory_positions()[0]
        result = agent.evaluate_product(pos)
        assert isinstance(result, ReorderNeed)


class TestI3Regression:

    def test_safety_stock_agent_loads(self):
        """TC-I5-78: I3 SafetyStockAgent still loads without error."""
        from app.services.safety_stock import SafetyStockAgent
        agent = SafetyStockAgent(data_dir=DATA_DIR)
        assert len(agent._forecasts) > 0

    def test_safety_stock_evaluates(self):
        """TC-I5-79: I3 evaluate_product still returns a SafetyStockTarget."""
        from app.services.safety_stock import SafetyStockAgent
        from app.models.safety_stock_target import SafetyStockTarget
        agent = SafetyStockAgent(data_dir=DATA_DIR)
        result = agent.evaluate_product("P001", "Bakery")
        assert result is not None
        target, ar = result
        assert isinstance(target, SafetyStockTarget)


class TestI4Regression:

    def test_stock_risk_agent_loads(self):
        """TC-I5-80: I4 StockRiskAgent still loads without error."""
        from app.services.stock_risk import StockRiskAgent
        agent = StockRiskAgent(data_dir=DATA_DIR)
        assert len(agent._products) > 0

    def test_stock_risk_evaluates(self):
        """TC-I5-81: I4 get_all_alerts() still returns alerts."""
        from app.services.stock_risk import StockRiskAgent
        agent = StockRiskAgent(data_dir=DATA_DIR)
        alerts = agent.get_all_alerts()
        assert isinstance(alerts, list)
