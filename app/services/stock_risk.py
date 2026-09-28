"""
I4 Expiry & Slow-Stock Agent — deterministic inventory risk identification.

Responsibility: identify which inventory is at risk due to:
  - EXPIRY_RISK  : inventory approaching shelf-life limit
  - SLOW_STOCK   : inventory moving slowly (days_of_cover > 30)
  - DEAD_STOCK   : positive inventory, zero sales in the observation window
  - EXCESS_STOCK : unusually high inventory relative to demand (days_of_cover > 60)

I4 does NOT:
  - calculate reorder quantities          (I2)
  - make purchasing decisions             (I2)
  - execute purchases                     (never)
  - modify inventory                      (never)
  - select suppliers                      (Procurement)
  - forecast demand                       (D4)
  - implement I5 exception escalation     (I5)
  - require Firestore, LLM, or internet   (offline-first MVP)

Rules (I4-v1)
─────────────
Observation window   : last 30 days of transaction history
Sales velocity       : total_units_sold_in_window / observation_days  (units/day)
Days of cover        : available_stock / sales_velocity
                       → None when velocity = 0 (avoid division-by-zero)
Dead stock           : available_stock > 0 AND velocity == 0
Slow stock           : days_of_cover > 30
Excess stock         : days_of_cover > 60
Inventory age        : today – date of most-recent RECEIPT movement for this product
                       → None when no RECEIPT movement is found
Days to expiry       : shelf_life_days – inventory_age_days
                       → None when shelf_life or age is unknown
Expiry HIGH          : days_to_expiry <= 7
Expiry MEDIUM        : days_to_expiry <= 14
No expiry risk       : days_to_expiry > 14 or data unavailable

Data source          : products.csv (shelf_life_days)
                       transactions.csv  (recent sales velocity)
                       inventory_movements.csv (RECEIPT dates for age)
                       inventory_snapshots.csv (available_stock via I1 pattern)

Uses only Python stdlib: csv, json, math, pathlib, datetime.
"""
from __future__ import annotations

import csv
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.stock_risk_alert import (
    StockRiskAlert,
    RISK_EXPIRY, RISK_SLOW, RISK_DEAD, RISK_EXCESS,
    SEV_HIGH, SEV_MEDIUM, SEV_LOW,
    highest_severity, FORMULA_VERSION,
)
from app.models.agent_result import AgentResult

# ── Constants ────────────────────────────────────────────────────────────────
AGENT_ID      = "I4"
ACTION_TYPE   = "FLAG_STOCK_RISK"
RULE_VERSION  = FORMULA_VERSION

OBSERVATION_DAYS        = 30   # look-back window for velocity
SLOW_STOCK_THRESHOLD    = 30   # days_of_cover > 30  → SLOW
EXCESS_STOCK_THRESHOLD  = 60   # days_of_cover > 60  → EXCESS
EXPIRY_HIGH_THRESHOLD   = 7    # days_to_expiry ≤ 7  → HIGH
EXPIRY_MEDIUM_THRESHOLD = 14   # days_to_expiry ≤ 14 → MEDIUM


# ── Pure calculation helpers (no side-effects) ────────────────────────────────

def calculate_sales_velocity(units_sold: float, observation_days: int) -> float:
    """
    Step 1: average daily demand over the observation window.

    Returns 0.0 when no sales exist (caller must handle dead-stock case).
    Raises ValueError for non-positive observation_days.
    """
    if observation_days <= 0:
        raise ValueError("observation_days must be positive")
    if units_sold < 0:
        raise ValueError("units_sold must be non-negative")
    return units_sold / observation_days


def calculate_days_of_cover(available_stock: float, sales_velocity: float) -> Optional[float]:
    """
    Step 2: how many days the current stock will last at the observed velocity.

    Returns None when velocity is 0 (dead stock; caller handles separately).
    Raises ValueError for negative available_stock or velocity.
    """
    if available_stock < 0:
        raise ValueError("available_stock must be non-negative")
    if sales_velocity < 0:
        raise ValueError("sales_velocity must be non-negative")
    if sales_velocity == 0.0:
        return None
    return available_stock / sales_velocity


def calculate_inventory_age(
    receipt_date: Optional[datetime],
    reference_date: Optional[datetime] = None,
) -> Optional[float]:
    """
    Step 3: age of the oldest stock in days since the most-recent receipt.

    Uses the most-recent RECEIPT movement date as a proxy for when the
    current batch arrived (MVP assumption: FIFO, single batch).
    Returns None when receipt_date is unknown.
    """
    if receipt_date is None:
        return None
    ref = reference_date or datetime.now(timezone.utc)
    # Ensure both are timezone-aware
    if receipt_date.tzinfo is None:
        receipt_date = receipt_date.replace(tzinfo=timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    delta = (ref - receipt_date).total_seconds() / 86_400
    return max(0.0, delta)


def calculate_days_to_expiry(
    shelf_life_days: Optional[int],
    inventory_age_days: Optional[float],
) -> Optional[float]:
    """
    Step 4: remaining shelf life in days.

    Returns None when either input is unavailable.
    """
    if shelf_life_days is None or inventory_age_days is None:
        return None
    return float(shelf_life_days) - inventory_age_days


def classify_expiry_risk(days_to_expiry: Optional[float]) -> Optional[str]:
    """
    Step 5: map days_to_expiry to severity.

    Returns None when expiry data is unavailable (no risk flag raised).
    HIGH   → days_to_expiry <= 7
    MEDIUM → days_to_expiry <= 14
    None   → no expiry risk / data unavailable
    """
    if days_to_expiry is None:
        return None
    if days_to_expiry <= EXPIRY_HIGH_THRESHOLD:
        return SEV_HIGH
    if days_to_expiry <= EXPIRY_MEDIUM_THRESHOLD:
        return SEV_MEDIUM
    return None


def classify_dead_stock(available_stock: float, sales_velocity: float) -> bool:
    """
    Step 6: identify dead stock.

    Dead stock: positive inventory with zero sales velocity.
    Zero stock is NOT dead stock.
    """
    return available_stock > 0 and sales_velocity == 0.0


def classify_slow_stock(days_of_cover: Optional[float]) -> Optional[str]:
    """
    Step 7: identify slow-moving stock.

    SLOW when days_of_cover > 30 and <= 60 (above 60 becomes EXCESS).
    Returns None when days_of_cover is None (dead stock case) or no risk.
    """
    if days_of_cover is None:
        return None
    if SLOW_STOCK_THRESHOLD < days_of_cover <= EXCESS_STOCK_THRESHOLD:
        return SEV_MEDIUM
    return None


def classify_excess_stock(days_of_cover: Optional[float]) -> Optional[str]:
    """
    Step 8: identify excess stock.

    HIGH when days_of_cover > 60.
    Returns None when days_of_cover is None or no risk.
    """
    if days_of_cover is None:
        return None
    if days_of_cover > EXCESS_STOCK_THRESHOLD:
        return SEV_HIGH
    return None


# ── StockRiskAgent ────────────────────────────────────────────────────────────

class StockRiskAgent:
    """
    I4 Expiry & Slow-Stock Agent.

    Reads:
      products.csv              — shelf_life_days
      transactions.csv          — recent sales velocity
      inventory_movements.csv   — RECEIPT dates (for inventory age)
      inventory_snapshots.csv   — latest available_stock

    Produces: List[StockRiskAlert] + List[AgentResult] per product.
    """

    def __init__(self, data_dir: Path, observation_days: int = OBSERVATION_DAYS):
        self._data_dir = Path(data_dir)
        self._observation_days = max(1, observation_days)
        self._products: Dict[str, dict]      = self._load_products()
        self._snapshots: Dict[str, dict]     = self._load_latest_snapshots()
        self._transactions: List[dict]        = self._load_transactions()
        self._movements: List[dict]           = self._load_movements()
        self._loaded_at = datetime.now(timezone.utc)

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_products(self) -> Dict[str, dict]:
        path = self._data_dir / "products.csv"
        products: Dict[str, dict] = {}
        with open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = row.get("product_id", "").strip().upper()
                if pid:
                    products[pid] = row
        return products

    def _load_latest_snapshots(self) -> Dict[str, dict]:
        """Return the most-recent snapshot row for each product."""
        path = self._data_dir / "inventory_snapshots.csv"
        latest: Dict[str, dict] = {}
        with open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = row.get("product_id", "").strip().upper()
                if not pid:
                    continue
                ts_str = row.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    continue
                if pid not in latest:
                    latest[pid] = row
                    latest[pid]["_ts"] = ts
                elif ts > latest[pid]["_ts"]:
                    latest[pid] = row
                    latest[pid]["_ts"] = ts
        return latest

    def _load_transactions(self) -> List[dict]:
        path = self._data_dir / "transactions.csv"
        rows: List[dict] = []
        with open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(row)
        return rows

    def _load_movements(self) -> List[dict]:
        path = self._data_dir / "inventory_movements.csv"
        rows: List[dict] = []
        with open(path, "r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(row)
        return rows

    # ── Derived data helpers ─────────────────────────────────────────────────

    def _units_sold_in_window(
        self, product_id: str, reference_date: Optional[datetime] = None
    ) -> float:
        """Sum transaction qty for this product within the observation window."""
        ref = reference_date or datetime.now(timezone.utc)
        cutoff = ref - timedelta(days=self._observation_days)
        total = 0.0
        for row in self._transactions:
            pid = row.get("product_id", "").strip().upper()
            if pid != product_id:
                continue
            ts_str = row.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                try:
                    qty = float(row.get("qty", 0))
                    if qty > 0:
                        total += qty
                except (ValueError, TypeError):
                    pass
        return total

    def _latest_receipt_date(self, product_id: str) -> Optional[datetime]:
        """Find the most-recent RECEIPT movement timestamp for this product."""
        latest: Optional[datetime] = None
        for row in self._movements:
            pid = row.get("product_id", "").strip().upper()
            if pid != product_id:
                continue
            move_type = row.get("type", "").strip().upper()
            if move_type != "RECEIPT":
                continue
            ts_str = row.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if latest is None or ts > latest:
                latest = ts
        return latest

    def _available_stock(self, product_id: str) -> float:
        """
        Compute available_stock from the latest snapshot.
        available_stock = stock_on_hand - reserved - damaged  (I1 formula)
        Returns 0.0 when no snapshot exists.
        """
        snap = self._snapshots.get(product_id)
        if snap is None:
            return 0.0
        try:
            soh      = float(snap.get("stock_on_hand", 0) or 0)
            reserved = float(snap.get("reserved", 0) or 0)
            damaged  = float(snap.get("damaged", 0) or 0)
            return max(0.0, soh - reserved - damaged)
        except (ValueError, TypeError):
            return 0.0

    def _shelf_life(self, product_id: str) -> Optional[int]:
        """Return shelf_life_days from products.csv, or None if unavailable."""
        prod = self._products.get(product_id)
        if prod is None:
            return None
        raw = prod.get("shelf_life_days", "").strip()
        if not raw:
            return None
        try:
            val = int(raw)
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None

    # ── Core evaluation ──────────────────────────────────────────────────────

    def evaluate_product(
        self,
        product_id: str,
        reference_date: Optional[datetime] = None,
    ) -> Tuple[List[StockRiskAlert], List[AgentResult]]:
        """
        Evaluate all risk types for one product.

        Returns a list of StockRiskAlert objects (one per risk type found)
        and a matching list of AgentResult objects.
        Returns ([], []) when the product has no data at all.

        Safe-failure: individual data gaps are tolerated; missing data is
        noted in the reason text, not invented.
        """
        pid = product_id.strip().upper()
        now = reference_date or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        alerts:  List[StockRiskAlert] = []
        results: List[AgentResult]    = []

        # ── Shared data ──────────────────────────────────────────────────────
        available_stock = self._available_stock(pid)
        units_sold      = self._units_sold_in_window(pid, reference_date=now)
        velocity        = calculate_sales_velocity(units_sold, self._observation_days)
        doc             = calculate_days_of_cover(available_stock, velocity)

        receipt_date    = self._latest_receipt_date(pid)
        age_days        = calculate_inventory_age(receipt_date, reference_date=now)
        shelf_life      = self._shelf_life(pid)
        days_to_expiry  = calculate_days_to_expiry(shelf_life, age_days)

        evidence = [pid]
        snap = self._snapshots.get(pid)
        if snap:
            evidence.append(snap.get("timestamp", "snapshot"))

        # ── 1. EXPIRY_RISK ────────────────────────────────────────────────────
        expiry_sev = classify_expiry_risk(days_to_expiry)
        if expiry_sev is not None and available_stock > 0:
            age_str = (
                f"{round(age_days, 1)} days old"
                if age_days is not None else "age unknown"
            )
            dte_str = (
                f"{round(days_to_expiry, 1)} days"
                if days_to_expiry is not None else "unknown"
            )
            reason = (
                f"Product has {round(available_stock)} units available. "
                f"Inventory is {age_str} against a {shelf_life}-day shelf life "
                f"({dte_str} remaining). Expiry risk: {expiry_sev}."
            )
            confidence = 0.90 if age_days is not None else 0.60
            alert = StockRiskAlert(
                product_id         = pid,
                risk_type          = RISK_EXPIRY,
                severity           = expiry_sev,
                available_stock    = available_stock,
                sales_velocity     = round(velocity, 4),
                days_of_cover      = round(doc, 2) if doc is not None else None,
                inventory_age_days = age_days,
                shelf_life_days    = shelf_life,
                days_to_expiry     = days_to_expiry,
                reason             = reason,
                evidence_refs      = list(evidence),
                confidence         = confidence,
                generated_at       = now,
            )
            alerts.append(alert)
            results.append(self._build_agent_result(alert, now))

        # ── 2. DEAD_STOCK ─────────────────────────────────────────────────────
        if classify_dead_stock(available_stock, velocity):
            sev = SEV_HIGH if available_stock >= 10 else SEV_MEDIUM
            reason = (
                f"Product has {round(available_stock)} units available but "
                f"no recorded sales in the last {self._observation_days} days. "
                f"Classified as dead stock."
            )
            alert = StockRiskAlert(
                product_id         = pid,
                risk_type          = RISK_DEAD,
                severity           = sev,
                available_stock    = available_stock,
                sales_velocity     = 0.0,
                days_of_cover      = None,
                inventory_age_days = age_days,
                shelf_life_days    = shelf_life,
                days_to_expiry     = days_to_expiry,
                reason             = reason,
                evidence_refs      = list(evidence),
                confidence         = 0.85,
                generated_at       = now,
            )
            alerts.append(alert)
            results.append(self._build_agent_result(alert, now))

        # Only evaluate SLOW/EXCESS when velocity > 0
        if velocity > 0:
            # ── 3. EXCESS_STOCK ───────────────────────────────────────────────
            excess_sev = classify_excess_stock(doc)
            if excess_sev is not None:
                reason = (
                    f"Product has approximately {round(doc, 1)} days of stock "  # type: ignore[arg-type]
                    f"cover based on a sales velocity of {round(velocity, 2)} units/day "
                    f"(last {self._observation_days} days). "
                    f"Excess stock threshold is {EXCESS_STOCK_THRESHOLD} days."
                )
                alert = StockRiskAlert(
                    product_id         = pid,
                    risk_type          = RISK_EXCESS,
                    severity           = excess_sev,
                    available_stock    = available_stock,
                    sales_velocity     = round(velocity, 4),
                    days_of_cover      = round(doc, 2) if doc is not None else None,
                    inventory_age_days = age_days,
                    shelf_life_days    = shelf_life,
                    days_to_expiry     = days_to_expiry,
                    reason             = reason,
                    evidence_refs      = list(evidence),
                    confidence         = 0.80,
                    generated_at       = now,
                )
                alerts.append(alert)
                results.append(self._build_agent_result(alert, now))

            # ── 4. SLOW_STOCK ─────────────────────────────────────────────────
            slow_sev = classify_slow_stock(doc)
            if slow_sev is not None:
                reason = (
                    f"Product has approximately {round(doc, 1)} days of stock "  # type: ignore[arg-type]
                    f"cover based on a sales velocity of {round(velocity, 2)} units/day "
                    f"(last {self._observation_days} days). "
                    f"Slow-stock threshold is {SLOW_STOCK_THRESHOLD} days."
                )
                alert = StockRiskAlert(
                    product_id         = pid,
                    risk_type          = RISK_SLOW,
                    severity           = slow_sev,
                    available_stock    = available_stock,
                    sales_velocity     = round(velocity, 4),
                    days_of_cover      = round(doc, 2) if doc is not None else None,
                    inventory_age_days = age_days,
                    shelf_life_days    = shelf_life,
                    days_to_expiry     = days_to_expiry,
                    reason             = reason,
                    evidence_refs      = list(evidence),
                    confidence         = 0.80,
                    generated_at       = now,
                )
                alerts.append(alert)
                results.append(self._build_agent_result(alert, now))

        return alerts, results

    # ── Public API ────────────────────────────────────────────────────────────

    def get_all_alerts(
        self,
        reference_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Return serialised risk alerts for all products with detected risks."""
        output: List[dict] = []
        for pid in self._products:
            alerts, agent_results = self.evaluate_product(pid, reference_date=reference_date)
            for alert, ar in zip(alerts, agent_results):
                output.append({**alert.to_dict(), "recommendation": ar.to_dict()})
        return output

    def get_alerts_for_product(
        self,
        product_id: str,
        reference_date: Optional[datetime] = None,
    ) -> Optional[List[dict]]:
        """
        Return serialised risk alerts for one product.

        Returns None when the product_id is not recognised.
        Returns [] when the product exists but has no active risk.
        """
        pid = product_id.strip().upper()
        if pid not in self._products:
            return None
        alerts, agent_results = self.evaluate_product(pid, reference_date=reference_date)
        return [
            {**alert.to_dict(), "recommendation": ar.to_dict()}
            for alert, ar in zip(alerts, agent_results)
        ]

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_agent_result(alert: StockRiskAlert, now: datetime) -> AgentResult:
        return AgentResult(
            recommendation_id    = f"I4-{uuid.uuid4().hex[:8].upper()}",
            agent_id             = AGENT_ID,
            entity_type          = "PRODUCT",
            entity_id            = alert.product_id,
            action_type          = ACTION_TYPE,
            action               = f"Flag {alert.risk_type} for product {alert.product_id}.",
            rationale            = alert.reason,
            evidence_refs        = list(alert.evidence_refs),
            confidence           = alert.confidence,
            risk_level           = alert.severity,
            requires_approval    = False,
            model_or_rule_version= RULE_VERSION,
            generated_at         = now,
            expires_at           = now + timedelta(hours=24),
        )
