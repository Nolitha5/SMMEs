"""
I5 — Inventory Exception Agent (I5-v1)

Detects inventory data and operational inconsistencies.

I5 does NOT:
  - calculate reorder points or quantities (I2)
  - calculate safety stock (I3)
  - classify expiry/slow-stock risk (I4)
  - make purchasing decisions or modify inventory
  - implement Procurement / R5

Data sources (all local CSVs, no internet required):
  - data/products.csv              → product catalogue
  - data/inventory_snapshots.csv   → stock positions over time
  - data/inventory_movements.csv   → individual stock movements
  - data/transactions.csv          → optional: used to cross-reference sales counts

Exception rules (I5-v1):
  1. NEGATIVE_STOCK             — available_stock < 0 in latest snapshot
  2. LARGE_STOCK_ADJUSTMENT     — |adjustment qty| >= 10 units (MEDIUM),
                                   >= 20 units (HIGH)
  3. MOVEMENT_SNAPSHOT_MISMATCH — net movements between consecutive snapshots
                                   don't reconcile with stock_on_hand change;
                                   tolerance = 2 units; >5 units = MEDIUM, >20 = HIGH
  4. RECEIPT_STOCK_MISMATCH     — receipt movement not followed by expected
                                   stock increase; requires R5 Procurement
                                   delivery data for full reconciliation
                                   (MVP: partial check only; full check deferred)
  5. DUPLICATE_SUSPICIOUS_MOVEMENT — duplicate movement_id, impossible values
                                      (RECEIPT qty <= 0, SALE qty <= 0 after negation
                                       in movement context, or identical records)

Future R5 hook:
  Pass procurement_deliveries (list[dict] with keys: product_id, delivered_qty,
  delivered_at) to evaluate_product() or get_all_exceptions() to enable full
  RECEIPT_STOCK_MISMATCH reconciliation.
"""
from __future__ import annotations

import csv
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.agent_result import AgentResult
from app.models.inventory_exception import (
    EXC_DUPLICATE_MOVEMENT,
    EXC_LARGE_ADJUSTMENT,
    EXC_MOVEMENT_SNAPSHOT_MISMATCH,
    EXC_NEGATIVE_STOCK,
    EXC_RECEIPT_STOCK_MISMATCH,
    FORMULA_VERSION,
    SEV_HIGH,
    SEV_LOW,
    SEV_MEDIUM,
    STATUS_OPEN,
    InventoryException,
)

# ── Thresholds (I5-v1) ────────────────────────────────────────────────────
LARGE_ADJ_MEDIUM_THRESHOLD = 10    # |adj_qty| >= this → MEDIUM
LARGE_ADJ_HIGH_THRESHOLD   = 20    # |adj_qty| >= this → HIGH
MISMATCH_TOLERANCE         = 2     # units; below this → not flagged
MISMATCH_MEDIUM_THRESHOLD  = 5     # units discrepancy → MEDIUM
MISMATCH_HIGH_THRESHOLD    = 20    # units discrepancy → HIGH

# Movement types
_TYPE_RECEIPT    = "RECEIPT"
_TYPE_SALE       = "SALE"
_TYPE_ADJUSTMENT = "ADJUSTMENT"
_TYPE_DAMAGE     = "DAMAGE"


# ── Pure calculation / detection functions ────────────────────────────────

def check_negative_stock(
    product_id: str,
    stock_on_hand: float,
    reserved: float,
    damaged: float,
    snapshot_timestamp: str,
) -> Optional[InventoryException]:
    """
    Rule 1 — NEGATIVE_STOCK.
    available_stock = stock_on_hand - reserved - damaged.
    If the result is < 0, this is an impossible inventory state.
    Severity is always HIGH.
    """
    available = stock_on_hand - reserved - damaged
    if available >= 0:
        return None

    return InventoryException(
        exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
        product_id      = product_id,
        exception_type  = EXC_NEGATIVE_STOCK,
        severity        = SEV_HIGH,
        status          = STATUS_OPEN,
        message         = (
            f"Available stock is {available:.1f} units — negative inventory is impossible."
        ),
        reason          = (
            f"Product {product_id} has stock_on_hand={stock_on_hand}, "
            f"reserved={reserved}, damaged={damaged}. "
            f"Available stock (stock_on_hand - reserved - damaged) = {available:.1f}, "
            f"which is below zero. This indicates an inventory recording error or "
            f"unrecorded stock movement."
        ),
        evidence_refs   = [
            f"inventory_snapshots.csv:{product_id}:{snapshot_timestamp}",
        ],
        affected_quantity = available,
        expected_value    = 0.0,
        actual_value      = available,
        confidence        = 1.0,
    )


def check_large_adjustment(
    product_id: str,
    movement_id: str,
    movement_type: str,
    qty: float,
    timestamp: str,
    available_stock: float,
) -> Optional[InventoryException]:
    """
    Rule 2 — LARGE_STOCK_ADJUSTMENT.
    Flags ADJUSTMENT or DAMAGE movements with unusually large absolute quantities.
    Thresholds:
      |qty| >= 20  → HIGH
      |qty| >= 10  → MEDIUM
    Also flags if |qty| >= 50% of available_stock (floor at MEDIUM severity).
    """
    if movement_type not in (_TYPE_ADJUSTMENT, _TYPE_DAMAGE):
        return None

    abs_qty = abs(qty)
    if abs_qty < LARGE_ADJ_MEDIUM_THRESHOLD:
        return None

    # Determine severity
    severity = SEV_MEDIUM
    if abs_qty >= LARGE_ADJ_HIGH_THRESHOLD:
        severity = SEV_HIGH
    elif available_stock > 0 and abs_qty >= 0.5 * available_stock:
        severity = SEV_MEDIUM  # large relative to stock but not >= 20 units

    pct = (abs_qty / available_stock * 100) if available_stock > 0 else float("inf")

    return InventoryException(
        exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
        product_id      = product_id,
        exception_type  = EXC_LARGE_ADJUSTMENT,
        severity        = severity,
        status          = STATUS_OPEN,
        message         = (
            f"Movement {movement_id} records a {movement_type} of "
            f"{qty:+.0f} units — unusually large adjustment."
        ),
        reason          = (
            f"Movement {movement_id} ({movement_type}) for product {product_id} "
            f"records an adjustment of {qty:+.0f} units on {timestamp}. "
            f"Absolute magnitude {abs_qty:.0f} units "
            f"({'%.0f%%' % pct} of available stock {available_stock:.0f}) "
            f"exceeds the large-adjustment threshold of "
            f"{LARGE_ADJ_MEDIUM_THRESHOLD} units (HIGH: {LARGE_ADJ_HIGH_THRESHOLD}). "
            f"This movement should be verified against a physical count or approval record."
        ),
        evidence_refs   = [
            f"inventory_movements.csv:{movement_id}",
            f"inventory_snapshots.csv:{product_id}",
        ],
        affected_quantity = qty,
        expected_value    = None,
        actual_value      = qty,
        confidence        = 0.9,
    )


def check_movement_snapshot_mismatch(
    product_id: str,
    opening_stock: float,
    closing_stock: float,
    opening_ts: str,
    closing_ts: str,
    net_movement: float,
    movement_ids: List[str],
) -> Optional[InventoryException]:
    """
    Rule 3 — MOVEMENT_SNAPSHOT_MISMATCH.
    Between two consecutive snapshots:
      expected_closing = opening_stock + net_movement
    If |expected_closing - closing_stock| > tolerance, flag an exception.

    Severity:
      discrepancy > 20 → HIGH
      discrepancy > 5  → MEDIUM
      <= tolerance (2) → no exception
    """
    expected = opening_stock + net_movement
    discrepancy = abs(expected - closing_stock)

    if discrepancy <= MISMATCH_TOLERANCE:
        return None

    severity = SEV_MEDIUM if discrepancy <= MISMATCH_HIGH_THRESHOLD else SEV_HIGH

    refs = [
        f"inventory_snapshots.csv:{product_id}:{opening_ts}",
        f"inventory_snapshots.csv:{product_id}:{closing_ts}",
    ] + [f"inventory_movements.csv:{mid}" for mid in movement_ids]

    return InventoryException(
        exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
        product_id      = product_id,
        exception_type  = EXC_MOVEMENT_SNAPSHOT_MISMATCH,
        severity        = severity,
        status          = STATUS_OPEN,
        message         = (
            f"Stock movements don't reconcile with snapshot change "
            f"for {product_id}: expected {expected:.1f}, recorded {closing_stock:.1f} "
            f"(gap {discrepancy:.1f} units)."
        ),
        reason          = (
            f"Between snapshots {opening_ts} (stock={opening_stock:.0f}) and "
            f"{closing_ts} (stock={closing_stock:.0f}), recorded movements sum to "
            f"net {net_movement:+.0f} units. "
            f"Expected closing stock = {expected:.1f}, "
            f"actual closing stock = {closing_stock:.1f}, "
            f"discrepancy = {discrepancy:.1f} units. "
            f"This suggests an unrecorded movement or an incorrect snapshot entry."
        ),
        evidence_refs   = refs,
        affected_quantity = discrepancy,
        expected_value    = expected,
        actual_value      = closing_stock,
        confidence        = 0.85,
    )


def check_receipt_stock_mismatch(
    product_id: str,
    movement_id: str,
    receipt_qty: float,
    stock_before: float,
    stock_after: float,
    receipt_ts: str,
    next_snapshot_ts: str,
    sales_in_period: float,
    r5_delivery_qty: Optional[float] = None,
) -> Optional[InventoryException]:
    """
    Rule 4 — RECEIPT_STOCK_MISMATCH.
    Checks whether a RECEIPT movement corresponds to a reasonable stock increase.

    MVP mode (r5_delivery_qty=None):
        Expected minimum stock_after = stock_before + receipt_qty - sales_in_period
        If stock_after < stock_before + receipt_qty - sales_in_period - tolerance,
        the receipt may not have been stocked or was double-counted.

    Full R5 mode (r5_delivery_qty provided):
        The R5 Procurement agent's confirmed delivery qty is compared against
        the receipt movement qty. If they differ by > tolerance, flag HIGH.

    Note: Full reconciliation requires R5 Procurement delivery data, which is
    not available in the local MVP (see architecture doc). This function
    provides a partial check and is ready for R5 integration with no rewrite.
    """
    if r5_delivery_qty is not None:
        # Full R5 mode
        diff = abs(r5_delivery_qty - receipt_qty)
        if diff <= MISMATCH_TOLERANCE:
            return None
        severity = SEV_HIGH if diff > MISMATCH_HIGH_THRESHOLD else SEV_MEDIUM
        return InventoryException(
            exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
            product_id      = product_id,
            exception_type  = EXC_RECEIPT_STOCK_MISMATCH,
            severity        = severity,
            status          = STATUS_OPEN,
            message         = (
                f"Receipt {movement_id} records {receipt_qty:.0f} units but "
                f"Procurement (R5) confirmed {r5_delivery_qty:.0f} units delivered "
                f"(gap {diff:.0f} units)."
            ),
            reason          = (
                f"The inventory receipt movement {movement_id} for product {product_id} "
                f"records {receipt_qty:.0f} units received on {receipt_ts}. "
                f"However, the R5 Procurement delivery confirmation indicates "
                f"{r5_delivery_qty:.0f} units were actually delivered "
                f"(discrepancy {diff:.0f} units). "
                f"This indicates a possible receiving error, partial delivery, "
                f"or data entry mistake."
            ),
            evidence_refs   = [
                f"inventory_movements.csv:{movement_id}",
                f"R5:procurement_delivery:{product_id}:{receipt_ts}",
            ],
            affected_quantity = diff,
            expected_value    = r5_delivery_qty,
            actual_value      = receipt_qty,
            confidence        = 0.95,
        )

    # MVP partial check: stock_after should be >= stock_before + receipt_qty - sales - tolerance
    expected_min = stock_before + receipt_qty - sales_in_period - MISMATCH_TOLERANCE
    if stock_after >= expected_min:
        return None

    discrepancy = expected_min - stock_after
    severity = SEV_HIGH if discrepancy > MISMATCH_HIGH_THRESHOLD else SEV_MEDIUM

    return InventoryException(
        exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
        product_id      = product_id,
        exception_type  = EXC_RECEIPT_STOCK_MISMATCH,
        severity        = severity,
        status          = STATUS_OPEN,
        message         = (
            f"Receipt {movement_id} of {receipt_qty:.0f} units for {product_id} "
            f"does not correspond to expected stock increase "
            f"(expected >= {expected_min:.1f}, actual {stock_after:.1f})."
        ),
        reason          = (
            f"RECEIPT movement {movement_id} for product {product_id} records "
            f"{receipt_qty:.0f} units received on {receipt_ts}. "
            f"Stock before receipt = {stock_before:.0f}. "
            f"Sales in period = {sales_in_period:.0f}. "
            f"Expected stock_on_hand after receipt (minimum) = {expected_min:.1f}, "
            f"actual stock_on_hand at {next_snapshot_ts} = {stock_after:.1f}. "
            f"NOTE: Full receipt reconciliation requires R5 Procurement "
            f"delivery data, which is not yet available in the local MVP."
        ),
        evidence_refs   = [
            f"inventory_movements.csv:{movement_id}",
            f"inventory_snapshots.csv:{product_id}:{next_snapshot_ts}",
        ],
        affected_quantity = discrepancy,
        expected_value    = expected_min,
        actual_value      = stock_after,
        confidence        = 0.75,  # lower confidence: MVP partial check only
    )


def check_duplicate_movements(
    product_id: str,
    movements: List[dict],
) -> List[InventoryException]:
    """
    Rule 5 — DUPLICATE_SUSPICIOUS_MOVEMENT.
    Detects:
      a) Duplicate movement_id (same ID appears more than once)
      b) Identical duplicate records (same product/type/qty/timestamp)
      c) Impossible movement values:
           - RECEIPT with qty <= 0
           - SALE with qty <= 0 (sales should be positive in this dataset)
    Returns a list (may be empty or contain multiple exceptions).
    """
    exceptions: List[InventoryException] = []

    # (a) Duplicate movement IDs
    seen_ids: Dict[str, int] = {}
    for m in movements:
        mid = m.get("movement_id", "")
        seen_ids[mid] = seen_ids.get(mid, 0) + 1
    for mid, count in seen_ids.items():
        if count > 1:
            exceptions.append(InventoryException(
                exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
                product_id      = product_id,
                exception_type  = EXC_DUPLICATE_MOVEMENT,
                severity        = SEV_MEDIUM,
                status          = STATUS_OPEN,
                message         = f"Movement ID '{mid}' appears {count} times for {product_id}.",
                reason          = (
                    f"Movement ID '{mid}' is recorded {count} times in "
                    f"inventory_movements.csv for product {product_id}. "
                    f"Each movement should have a unique ID. "
                    f"Duplicate records may cause double-counting."
                ),
                evidence_refs   = [f"inventory_movements.csv:{mid}"],
                affected_quantity = None,
                expected_value    = 1.0,
                actual_value      = float(count),
                confidence        = 1.0,
            ))

    # (b) Identical duplicate records (product_id + type + qty + timestamp)
    seen_records: Dict[Tuple, int] = {}
    for m in movements:
        key = (m.get("product_id", ""), m.get("type", ""), m.get("qty", ""), m.get("timestamp", ""))
        seen_records[key] = seen_records.get(key, 0) + 1
    for key, count in seen_records.items():
        if count > 1:
            pid, mtype, qty, ts = key
            exceptions.append(InventoryException(
                exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
                product_id      = product_id,
                exception_type  = EXC_DUPLICATE_MOVEMENT,
                severity        = SEV_MEDIUM,
                status          = STATUS_OPEN,
                message         = (
                    f"Duplicate {mtype} record: {qty} units on {ts} "
                    f"appears {count} times."
                ),
                reason          = (
                    f"An identical inventory record ({mtype}, {qty} units, {ts}) "
                    f"for product {product_id} appears {count} times. "
                    f"This is likely a data-entry duplicate and may cause "
                    f"double-counting in reconciliation."
                ),
                evidence_refs   = [f"inventory_movements.csv:{product_id}:{ts}"],
                affected_quantity = None,
                expected_value    = 1.0,
                actual_value      = float(count),
                confidence        = 0.95,
            ))

    # (c) Impossible values
    for m in movements:
        mid   = m.get("movement_id", "?")
        mtype = m.get("type", "")
        ts    = m.get("timestamp", "")
        try:
            qty = float(m.get("qty", 0))
        except (ValueError, TypeError):
            qty = 0.0

        if mtype == "RECEIPT" and qty <= 0:
            exceptions.append(InventoryException(
                exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
                product_id      = product_id,
                exception_type  = EXC_DUPLICATE_MOVEMENT,
                severity        = SEV_HIGH,
                status          = STATUS_OPEN,
                message         = (
                    f"RECEIPT movement {mid} records non-positive quantity ({qty:.0f})."
                ),
                reason          = (
                    f"Movement {mid} is a RECEIPT but records qty={qty:.0f} for "
                    f"product {product_id} on {ts}. A goods receipt must have a "
                    f"positive quantity. This is an impossible movement value."
                ),
                evidence_refs   = [f"inventory_movements.csv:{mid}"],
                affected_quantity = qty,
                expected_value    = None,
                actual_value      = qty,
                confidence        = 1.0,
            ))
        elif mtype == "SALE" and qty <= 0:
            exceptions.append(InventoryException(
                exception_id    = f"I5-{uuid.uuid4().hex[:12].upper()}",
                product_id      = product_id,
                exception_type  = EXC_DUPLICATE_MOVEMENT,
                severity        = SEV_MEDIUM,
                status          = STATUS_OPEN,
                message         = (
                    f"SALE movement {mid} records non-positive quantity ({qty:.0f})."
                ),
                reason          = (
                    f"Movement {mid} is a SALE but records qty={qty:.0f} for "
                    f"product {product_id} on {ts}. Sales should record positive "
                    f"outgoing quantities. This may indicate a data-entry error "
                    f"(possibly a return that should be recorded as an ADJUSTMENT)."
                ),
                evidence_refs   = [f"inventory_movements.csv:{mid}"],
                affected_quantity = qty,
                expected_value    = None,
                actual_value      = qty,
                confidence        = 0.9,
            ))

    return exceptions


def _build_agent_result(exc: InventoryException, now: datetime) -> AgentResult:
    """Wrap an InventoryException in the shared AgentResult contract."""
    from datetime import timedelta
    return AgentResult(
        recommendation_id     = f"I5-AR-{exc.exception_id}",
        agent_id              = "I5",
        entity_type           = "PRODUCT",
        entity_id             = exc.product_id,
        action_type           = "FLAG_INVENTORY_EXCEPTION",
        action                = f"REVIEW_{exc.exception_type}",
        rationale             = exc.reason,
        evidence_refs         = exc.evidence_refs,
        confidence            = exc.confidence,
        risk_level            = exc.severity,
        requires_approval     = False,
        model_or_rule_version = exc.formula_version,
        generated_at          = now,
        expires_at            = now + timedelta(days=1),
    )


# ── Agent class ──────────────────────────────────────────────────────────

class InventoryExceptionAgent:
    """
    I5 — Inventory Exception Agent.

    Loaded once at startup; all state is read-only in-memory.

    Future R5 hook:
        Pass `procurement_deliveries` (list[dict] with keys:
        product_id, delivered_qty, delivered_at) to get_all_exceptions()
        or evaluate_product() to enable full RECEIPT_STOCK_MISMATCH checks.
    """

    def __init__(self, data_dir: Path, observation_days: int = 30):
        self._data_dir         = Path(data_dir)
        self._observation_days = observation_days
        self._products         = self._load_products()
        self._snapshots        = self._load_all_snapshots()
        self._movements        = self._load_movements()
        self._loaded_at        = datetime.now(timezone.utc)

    # ── Data loaders ─────────────────────────────────────────────────────

    def _load_products(self) -> Dict[str, dict]:
        products = {}
        path = self._data_dir / "products.csv"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                products[row["product_id"].strip()] = row
        return products

    def _load_all_snapshots(self) -> List[dict]:
        """Load all snapshot records sorted by timestamp ascending."""
        rows = []
        path = self._data_dir / "inventory_snapshots.csv"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        rows.sort(key=lambda r: r["timestamp"])
        return rows

    def _load_movements(self) -> List[dict]:
        """Load all inventory movements sorted by timestamp ascending."""
        rows = []
        path = self._data_dir / "inventory_movements.csv"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        rows.sort(key=lambda r: r["timestamp"])
        return rows

    # ── Snapshot helpers ──────────────────────────────────────────────────

    def _latest_snapshot(self, product_id: str) -> Optional[dict]:
        """Return the most-recent snapshot row for a product."""
        latest = None
        for row in self._snapshots:
            if row["product_id"].strip() == product_id:
                if latest is None or row["timestamp"] > latest["timestamp"]:
                    latest = row
        return latest

    def _snapshots_for_product(self, product_id: str) -> List[dict]:
        """All snapshot rows for a product, sorted ascending."""
        return [r for r in self._snapshots if r["product_id"].strip() == product_id]

    def _available_stock(self, snap: dict) -> float:
        try:
            soh = float(snap.get("stock_on_hand", 0) or 0)
            res = float(snap.get("reserved", 0) or 0)
            dmg = float(snap.get("damaged", 0) or 0)
            return soh - res - dmg
        except (ValueError, TypeError):
            return 0.0

    # ── Movement helpers ──────────────────────────────────────────────────

    def _movements_for_product(self, product_id: str) -> List[dict]:
        return [m for m in self._movements if m.get("product_id", "").strip() == product_id]

    def _net_movement_between(
        self,
        product_id: str,
        start_ts: str,
        end_ts: str,
    ) -> Tuple[float, List[str]]:
        """
        Sum net stock change from movements between two snapshot timestamps.
        Returns (net_qty, list_of_movement_ids).
        Movement sign convention (what each type does to stock_on_hand):
          RECEIPT   +qty
          SALE      -qty   (qty is stored as positive)
          ADJUSTMENT qty   (stored as signed: negative = removal)
          DAMAGE    qty    (stored as negative)
        """
        net = 0.0
        ids = []
        for m in self._movements:
            if m.get("product_id", "").strip() != product_id:
                continue
            ts = m.get("timestamp", "")
            if ts <= start_ts or ts > end_ts:
                continue
            try:
                qty = float(m.get("qty", 0) or 0)
            except (ValueError, TypeError):
                continue
            mtype = m.get("type", "").strip().upper()
            if mtype == _TYPE_RECEIPT:
                net += qty
            elif mtype == _TYPE_SALE:
                net -= qty   # sales reduce stock
            else:
                # ADJUSTMENT and DAMAGE are stored as signed (negative = removal)
                net += qty
            ids.append(m.get("movement_id", "?"))
        return net, ids

    # ── Core evaluation ───────────────────────────────────────────────────

    def evaluate_product(
        self,
        product_id: str,
        reference_date: Optional[datetime] = None,
        procurement_deliveries: Optional[List[dict]] = None,
    ) -> Optional[Tuple[List[InventoryException], List[AgentResult]]]:
        """
        Evaluate all I5 exception rules for one product.

        Returns:
            None                           — product not found
            ([], [])                       — product found, no exceptions
            ([InventoryException, ...], [AgentResult, ...])  — active exceptions

        Args:
            product_id: the product to evaluate
            reference_date: override for "today" (testing/backfill use)
            procurement_deliveries: optional R5 delivery facts for full
                RECEIPT_STOCK_MISMATCH checks (list of dicts with keys:
                product_id, delivered_qty, delivered_at).
                Pass None to use MVP partial check only.
        """
        pid = product_id.strip().upper()
        if pid not in self._products:
            return None

        now = reference_date or datetime.now(timezone.utc)
        exceptions: List[InventoryException] = []

        # ── Rule 1: NEGATIVE_STOCK ────────────────────────────────────────
        latest_snap = self._latest_snapshot(pid)
        if latest_snap:
            try:
                soh = float(latest_snap.get("stock_on_hand", 0) or 0)
                res = float(latest_snap.get("reserved", 0) or 0)
                dmg = float(latest_snap.get("damaged", 0) or 0)
            except (ValueError, TypeError):
                soh, res, dmg = 0.0, 0.0, 0.0
            exc = check_negative_stock(
                pid, soh, res, dmg, latest_snap.get("timestamp", "")
            )
            if exc:
                exceptions.append(exc)

        # ── Rule 2: LARGE_STOCK_ADJUSTMENT ───────────────────────────────
        avail = self._available_stock(latest_snap) if latest_snap else 0.0
        for m in self._movements_for_product(pid):
            try:
                qty = float(m.get("qty", 0) or 0)
            except (ValueError, TypeError):
                qty = 0.0
            exc = check_large_adjustment(
                product_id   = pid,
                movement_id  = m.get("movement_id", "?"),
                movement_type = m.get("type", "").strip().upper(),
                qty          = qty,
                timestamp    = m.get("timestamp", ""),
                available_stock = avail,
            )
            if exc:
                exceptions.append(exc)

        # ── Rule 3: MOVEMENT_SNAPSHOT_MISMATCH ───────────────────────────
        snaps = self._snapshots_for_product(pid)
        for i in range(len(snaps) - 1):
            s1, s2 = snaps[i], snaps[i + 1]
            t1, t2 = s1["timestamp"], s2["timestamp"]
            soh1 = float(s1.get("stock_on_hand", 0) or 0)
            soh2 = float(s2.get("stock_on_hand", 0) or 0)
            net, move_ids = self._net_movement_between(pid, t1, t2)
            exc = check_movement_snapshot_mismatch(
                product_id   = pid,
                opening_stock = soh1,
                closing_stock = soh2,
                opening_ts    = t1,
                closing_ts    = t2,
                net_movement  = net,
                movement_ids  = move_ids,
            )
            if exc:
                exceptions.append(exc)

        # ── Rule 4: RECEIPT_STOCK_MISMATCH (MVP partial check) ────────────
        # Deliver full check when R5 procurement_deliveries are provided.
        # MVP: check each RECEIPT movement against the stock change in the
        # following snapshot period.
        r5_lookup: Dict[str, float] = {}
        if procurement_deliveries:
            for d in procurement_deliveries:
                if d.get("product_id", "").strip().upper() == pid:
                    r5_lookup[d.get("delivered_at", "")] = float(d.get("delivered_qty", 0))

        receipt_moves = [
            m for m in self._movements_for_product(pid)
            if m.get("type", "").strip().upper() == _TYPE_RECEIPT
        ]
        for rm in receipt_moves:
            rm_ts  = rm.get("timestamp", "")
            mid    = rm.get("movement_id", "?")
            try:
                r_qty = float(rm.get("qty", 0) or 0)
            except (ValueError, TypeError):
                continue
            if r_qty <= 0:
                continue  # already caught by Rule 5

            # Find the snapshot immediately before and after the receipt
            snap_before = None
            snap_after  = None
            for s in snaps:
                if s["timestamp"] <= rm_ts:
                    snap_before = s
                else:
                    snap_after = s
                    break

            if snap_before is None or snap_after is None:
                continue

            try:
                soh_before = float(snap_before.get("stock_on_hand", 0) or 0)
                soh_after  = float(snap_after.get("stock_on_hand", 0) or 0)
            except (ValueError, TypeError):
                continue

            # Sales between the two snapshots
            sales_net = 0.0
            for m in self._movements_for_product(pid):
                mts = m.get("timestamp", "")
                if mts <= snap_before["timestamp"] or mts > snap_after["timestamp"]:
                    continue
                if m.get("type", "").strip().upper() == _TYPE_SALE:
                    try:
                        sales_net += float(m.get("qty", 0) or 0)
                    except (ValueError, TypeError):
                        pass

            r5_qty = r5_lookup.get(rm_ts)

            exc = check_receipt_stock_mismatch(
                product_id      = pid,
                movement_id     = mid,
                receipt_qty     = r_qty,
                stock_before    = soh_before,
                stock_after     = soh_after,
                receipt_ts      = rm_ts,
                next_snapshot_ts = snap_after["timestamp"],
                sales_in_period  = sales_net,
                r5_delivery_qty  = r5_qty,
            )
            if exc:
                exceptions.append(exc)

        # ── Rule 5: DUPLICATE / SUSPICIOUS MOVEMENTS ─────────────────────
        dup_excs = check_duplicate_movements(pid, self._movements_for_product(pid))
        exceptions.extend(dup_excs)

        # ── Build AgentResult for each exception ──────────────────────────
        agent_results = [_build_agent_result(e, now) for e in exceptions]

        return exceptions, agent_results

    def get_all_exceptions(
        self,
        reference_date: Optional[datetime] = None,
        procurement_deliveries: Optional[List[dict]] = None,
    ) -> List[dict]:
        """
        Evaluate all products and return a flat list of exception dicts.
        Products with no exceptions are excluded from the output.
        """
        results = []
        for pid in sorted(self._products.keys()):
            outcome = self.evaluate_product(pid, reference_date, procurement_deliveries)
            if outcome is None:
                continue
            excs, ars = outcome
            for exc, ar in zip(excs, ars):
                results.append({
                    **exc.to_dict(),
                    "agent_result": ar.to_dict(),
                })
        return results

    def get_exceptions_for_product(
        self,
        product_id: str,
        reference_date: Optional[datetime] = None,
        procurement_deliveries: Optional[List[dict]] = None,
    ) -> Optional[List[dict]]:
        """
        Return exceptions for one product.
        Returns None if product_id is unknown (→ HTTP 404).
        Returns []   if product is known but has no active exceptions.
        """
        pid = product_id.strip().upper()
        outcome = self.evaluate_product(pid, reference_date, procurement_deliveries)
        if outcome is None:
            return None
        excs, ars = outcome
        return [
            {**exc.to_dict(), "agent_result": ar.to_dict()}
            for exc, ar in zip(excs, ars)
        ]
