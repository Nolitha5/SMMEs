"""
I3 Safety Stock Agent — SafetyStockTarget output contract.

This is the formal output contract produced by the I3 Safety Stock Agent.
It is consumed by I2 (ReorderPointAgent) as the safety_stock input parameter.

Fields:
    product_id          — product identifier
    safety_stock        — ceil(raw_safety_stock), never negative (integer units)
    expected_daily_demand — Step 1: expected_qty / horizon
    forecast_uncertainty  — Step 3: daily_std = horizon_std / sqrt(horizon)
    lead_time_days      — supplier lead time in days
    reliability_score   — raw supplier reliability score (0–1)
    reliability_factor  — Step 6: 1 + (1 - reliability_score), clamped 0–1 input
    service_level       — z-score service level (e.g. 0.95)
    z_score             — mapped z-value for the service level
    raw_safety_stock    — Step 7: z * lead_time_demand_std * reliability_factor
    confidence          — "HIGH" / "MEDIUM" / "LOW" based on forecast confidence
    reason              — human-readable explanation
    formula_version     — "I3-v1"
    generated_at        — ISO-8601 timestamp
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SafetyStockTarget:
    product_id: str
    safety_stock: int                  # ceil(raw), never negative
    expected_daily_demand: float
    forecast_uncertainty: float        # daily_std
    lead_time_days: int
    reliability_score: float           # raw supplier score 0–1
    reliability_factor: float          # 1 + (1 - reliability_score)
    service_level: float               # e.g. 0.95
    z_score: float                     # e.g. 1.65
    raw_safety_stock: float
    confidence: str                    # HIGH / MEDIUM / LOW
    reason: str
    formula_version: str = "I3-v1"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "safety_stock": self.safety_stock,
            "expected_daily_demand": round(self.expected_daily_demand, 4),
            "forecast_uncertainty": round(self.forecast_uncertainty, 4),
            "lead_time_days": self.lead_time_days,
            "reliability_score": round(self.reliability_score, 4),
            "reliability_factor": round(self.reliability_factor, 4),
            "service_level": self.service_level,
            "z_score": self.z_score,
            "raw_safety_stock": round(self.raw_safety_stock, 4),
            "confidence": self.confidence,
            "reason": self.reason,
            "formula_version": self.formula_version,
            "generated_at": self.generated_at,
        }
