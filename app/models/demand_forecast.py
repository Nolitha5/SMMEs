"""
DemandForecast model — shared contract between Demand Sensing and Inventory Management.

This model is the I1 reader side of the Demand → Inventory handoff.
I1 reads demand_forecasts.json but does NOT generate forecasts itself.
I2 (Reorder Point) and I3 (Safety Stock) will consume this contract.

Shared contract schema:
    product_id, horizon, expected_qty, lower_bound, upper_bound,
    confidence, drivers, generated_at, source
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class DemandForecast:
    """
    A demand forecast produced by the Demand Sensing team (Member 1).
    I1 treats this as a read-only input — never modifies it.

    The `source` field discriminates:
        "mock_demand_forecast" — placeholder data (current state)
        "demand_forecast_v1"   — real output from Member 1's model (future)
    """

    product_id: str
    horizon: int                    # Forecast horizon in days (typically 7)
    expected_qty: float             # Point estimate for the horizon
    lower_bound: float              # Lower confidence interval
    upper_bound: float              # Upper confidence interval
    confidence: float               # Forecast confidence (0-1)
    drivers: List[str]              # Features driving this forecast
    generated_at: datetime
    source: str = "mock_demand_forecast"

    @property
    def daily_rate(self) -> float:
        """Average daily demand derived from the horizon forecast."""
        if self.horizon <= 0:
            return 0.0
        return self.expected_qty / self.horizon

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "horizon": self.horizon,
            "expected_qty": self.expected_qty,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence": self.confidence,
            "drivers": self.drivers,
            "generated_at": self.generated_at.isoformat(),
            "source": self.source,
            "daily_rate": round(self.daily_rate, 3),
        }
