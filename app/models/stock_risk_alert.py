"""
StockRiskAlert — output contract for I4 Expiry & Slow-Stock Agent.

I4 identifies inventory risk for each product and publishes this contract.
I4 does NOT place orders, modify inventory, or make purchasing decisions.
Reorder decisions remain the responsibility of I2.

Risk types:
    EXPIRY_RISK  — product is approaching or past its shelf-life limit
    SLOW_STOCK   — product has positive inventory but moves slowly (days_of_cover > 30)
    DEAD_STOCK   — product has positive inventory but zero recorded sales in the window
    EXCESS_STOCK — inventory is unusually high relative to recent demand (days_of_cover > 60)

Severity:
    HIGH   — imminent expiry (<= 7 days), dead stock with significant inventory,
              or extremely high days of cover (> 60)
    MEDIUM — approaching expiry (<= 14 days), slow-moving stock (> 30 days cover)
    LOW    — weaker warning conditions

Formula version: I4-v1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


# ── Risk type constants ─────────────────────────────────────────────────────
RISK_EXPIRY   = "EXPIRY_RISK"
RISK_SLOW     = "SLOW_STOCK"
RISK_DEAD     = "DEAD_STOCK"
RISK_EXCESS   = "EXCESS_STOCK"

# Severity constants
SEV_HIGH   = "HIGH"
SEV_MEDIUM = "MEDIUM"
SEV_LOW    = "LOW"

# Rule version
FORMULA_VERSION = "I4-v1"

# Severity ordering for comparison
_SEV_ORDER = {SEV_HIGH: 3, SEV_MEDIUM: 2, SEV_LOW: 1}


def highest_severity(severities: List[str]) -> str:
    """Return the highest severity from a list; defaults to LOW."""
    if not severities:
        return SEV_LOW
    return max(severities, key=lambda s: _SEV_ORDER.get(s, 0))


@dataclass
class StockRiskAlert:
    """
    I4 output contract — one alert per (product, risk_type) combination.

    A product may have multiple StockRiskAlert objects (e.g. both
    SLOW_STOCK and EXPIRY_RISK).
    """

    product_id:         str
    risk_type:          str           # EXPIRY_RISK | SLOW_STOCK | DEAD_STOCK | EXCESS_STOCK
    severity:           str           # HIGH | MEDIUM | LOW
    available_stock:    float         # units available at evaluation time

    # Velocity / cover
    sales_velocity:     Optional[float]   # units/day; None if not calculable
    days_of_cover:      Optional[float]   # available_stock / sales_velocity; None if velocity=0

    # Expiry
    inventory_age_days: Optional[float]   # age of oldest receipt batch in days
    shelf_life_days:    Optional[int]     # from products.csv (None if not available)
    days_to_expiry:     Optional[float]   # shelf_life_days - inventory_age_days

    # Explanation
    reason:             str           # human-readable explanation
    evidence_refs:      List[str]     # product_id, snapshot timestamps, etc.
    confidence:         float         # 0.0–1.0
    generated_at:       datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    formula_version:    str = FORMULA_VERSION

    def to_dict(self) -> dict:
        return {
            "product_id":         self.product_id,
            "risk_type":          self.risk_type,
            "severity":           self.severity,
            "available_stock":    self.available_stock,
            "sales_velocity":     (
                round(self.sales_velocity, 4)
                if self.sales_velocity is not None else None
            ),
            "days_of_cover":      (
                round(self.days_of_cover, 2)
                if self.days_of_cover is not None else None
            ),
            "inventory_age_days": (
                round(self.inventory_age_days, 1)
                if self.inventory_age_days is not None else None
            ),
            "shelf_life_days":    self.shelf_life_days,
            "days_to_expiry":     (
                round(self.days_to_expiry, 1)
                if self.days_to_expiry is not None else None
            ),
            "reason":             self.reason,
            "evidence_refs":      self.evidence_refs,
            "confidence":         round(self.confidence, 4),
            "generated_at":       self.generated_at.isoformat(),
            "formula_version":    self.formula_version,
        }
