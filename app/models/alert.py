"""Alert domain model — I1 Stock Monitor."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StockStatus(str, Enum):
    """
    I1 stock classification derived from available_stock vs demand forecast.

    Classification rules (in priority order):
        OUT_OF_STOCK   : available_stock <= 0
        CRITICAL       : 0 < days_of_supply < CRITICAL_DAYS (default: 2)
        STOCK_PRESSURE : days_of_supply < PRESSURE_DAYS (default: 7) AND
                         (available + in_transit) < expected_demand
        LOW            : days_of_supply < LOW_DAYS (default: 7) but pressure is eased
        HEALTHY        : days_of_supply >= LOW_DAYS
    """

    HEALTHY = "HEALTHY"
    LOW = "LOW"
    CRITICAL = "CRITICAL"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    STOCK_PRESSURE = "STOCK_PRESSURE"


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertType(str, Enum):
    OUT_OF_STOCK = "OUT_OF_STOCK"
    CRITICAL_STOCK = "CRITICAL_STOCK"
    STOCK_PRESSURE = "STOCK_PRESSURE"
    LOW_STOCK = "LOW_STOCK"
    APPROACHING_LOW = "APPROACHING_LOW"


# Map stock status → alert severity
STATUS_SEVERITY_MAP = {
    StockStatus.OUT_OF_STOCK: AlertSeverity.CRITICAL,
    StockStatus.CRITICAL: AlertSeverity.CRITICAL,
    StockStatus.STOCK_PRESSURE: AlertSeverity.HIGH,
    StockStatus.LOW: AlertSeverity.MEDIUM,
    StockStatus.HEALTHY: AlertSeverity.INFO,
}

# Map stock status → alert type
STATUS_ALERT_TYPE_MAP = {
    StockStatus.OUT_OF_STOCK: AlertType.OUT_OF_STOCK,
    StockStatus.CRITICAL: AlertType.CRITICAL_STOCK,
    StockStatus.STOCK_PRESSURE: AlertType.STOCK_PRESSURE,
    StockStatus.LOW: AlertType.LOW_STOCK,
}


@dataclass
class Alert:
    """An inventory alert raised by the I1 Stock Monitor."""

    alert_id: str
    product_id: str
    product_name: str
    store_id: str
    stock_status: StockStatus
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    available_stock: float
    stock_on_hand: float
    reserved: float
    damaged: float
    in_transit: float
    days_of_supply: float       # available / daily_demand_rate
    expected_7d_demand: float   # from demand forecast
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "store_id": self.store_id,
            "stock_status": self.stock_status.value,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "available_stock": self.available_stock,
            "stock_on_hand": self.stock_on_hand,
            "reserved": self.reserved,
            "damaged": self.damaged,
            "in_transit": self.in_transit,
            "days_of_supply": round(self.days_of_supply, 1),
            "expected_7d_demand": self.expected_7d_demand,
            "generated_at": self.generated_at.isoformat(),
        }
