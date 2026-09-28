"""
InventoryException — output contract for I5 Inventory Exception Agent.

I5 identifies inventory data or operational inconsistencies that require
attention.  It does NOT:
  - calculate reorder points or quantities (I2)
  - calculate safety stock (I3)
  - classify expiry/slow-stock risk (I4)
  - make purchasing decisions
  - execute purchases
  - modify inventory
  - implement Procurement / R5

Exception types:
    NEGATIVE_STOCK             — available_stock < 0 (impossible inventory state)
    LARGE_STOCK_ADJUSTMENT     — adjustment/damage movement unusually large vs stock level
    MOVEMENT_SNAPSHOT_MISMATCH — recorded movements don't reconcile with snapshot change
    RECEIPT_STOCK_MISMATCH     — receipt movement doesn't correspond to expected stock increase
                                 NOTE: full reconciliation requires R5 Procurement delivery
                                 data, which is not yet available in the local MVP.
    DUPLICATE_SUSPICIOUS_MOVEMENT — duplicate movement_id, impossible movement values,
                                    or identical duplicate records

Status:
    OPEN — newly detected; no resolution workflow yet (planned for I5 v2)

Formula version: I5-v1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

# ── Exception type constants ────────────────────────────────────────────────
EXC_NEGATIVE_STOCK             = "NEGATIVE_STOCK"
EXC_LARGE_ADJUSTMENT           = "LARGE_STOCK_ADJUSTMENT"
EXC_MOVEMENT_SNAPSHOT_MISMATCH = "MOVEMENT_SNAPSHOT_MISMATCH"
EXC_RECEIPT_STOCK_MISMATCH     = "RECEIPT_STOCK_MISMATCH"
EXC_DUPLICATE_MOVEMENT         = "DUPLICATE_SUSPICIOUS_MOVEMENT"

# ── Severity constants ────────────────────────────────────────────────────
SEV_HIGH   = "HIGH"
SEV_MEDIUM = "MEDIUM"
SEV_LOW    = "LOW"

# ── Status constants ──────────────────────────────────────────────────────
STATUS_OPEN = "OPEN"

# ── Rule version ──────────────────────────────────────────────────────────
FORMULA_VERSION = "I5-v1"

# ── Severity ordering ─────────────────────────────────────────────────────
_SEV_ORDER = {SEV_HIGH: 3, SEV_MEDIUM: 2, SEV_LOW: 1}


def highest_severity(severities: List[str]) -> str:
    """Return the highest severity from a list; defaults to LOW."""
    if not severities:
        return SEV_LOW
    return max(severities, key=lambda s: _SEV_ORDER.get(s, 0))


@dataclass
class InventoryException:
    """
    I5 output contract — one record per (product, exception_type) combination.

    A product may have multiple InventoryException records simultaneously.
    All exceptions are status=OPEN on creation; resolution workflow is future scope.

    Future R5 integration:
        When the Procurement / R5 agent is available, pass its delivery facts
        to InventoryExceptionAgent.evaluate_product() via the optional
        `procurement_deliveries` parameter. The RECEIPT_STOCK_MISMATCH check
        will use that data for full reconciliation. No code rewrite is needed.
    """

    exception_id:       str
    product_id:         str
    exception_type:     str           # one of the EXC_* constants
    severity:           str           # HIGH | MEDIUM | LOW
    status:             str           # OPEN (future: RESOLVED | ACKNOWLEDGED)
    message:            str           # short human-readable summary
    reason:             str           # detailed explanation (WHAT / WHY / evidence)

    # Evidence
    evidence_refs:      List[str]     # CSV sources, movement_ids, snapshot timestamps

    # Quantitative context
    affected_quantity:  Optional[float]  # e.g. the negative stock qty or adjustment size
    expected_value:     Optional[float]  # what the system expected (e.g. expected stock change)
    actual_value:       Optional[float]  # what was observed

    # Provenance
    generated_at:       datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    formula_version:    str = FORMULA_VERSION
    confidence:         float = 1.0   # 0.0–1.0; deterministic rules default to 1.0

    def to_dict(self) -> dict:
        return {
            "exception_id":       self.exception_id,
            "product_id":         self.product_id,
            "exception_type":     self.exception_type,
            "severity":           self.severity,
            "status":             self.status,
            "message":            self.message,
            "reason":             self.reason,
            "evidence_refs":      self.evidence_refs,
            "affected_quantity":  self.affected_quantity,
            "expected_value":     self.expected_value,
            "actual_value":       self.actual_value,
            "generated_at":       self.generated_at.isoformat(),
            "formula_version":    self.formula_version,
            "confidence":         round(self.confidence, 4),
        }
