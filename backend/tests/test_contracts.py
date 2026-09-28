from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.contracts.models import DemandForecast, GoodsReceipt, PurchaseRecommendation, RiskLevel


def test_demand_forecast_parses_pipe_drivers():
    f = DemandForecast(product_id="SKU", horizon_days=7, expected_qty=10, lower_bound=8, upper_bound=12, confidence=.8, drivers="promo|weekend")
    assert f.drivers == ["promo", "weekend"]


def test_demand_forecast_rejects_invalid_bounds():
    with pytest.raises(ValidationError):
        DemandForecast(product_id="SKU", horizon_days=7, expected_qty=10, lower_bound=11, upper_bound=12, confidence=.8)


def test_goods_receipt_rejects_defects_above_received():
    with pytest.raises(ValidationError):
        GoodsReceipt(receipt_id="R", po_id="P", supplier_id="S", product_id="SKU", qty_received=2, qty_defective=3)


def test_purchase_recommendation_contract():
    p = PurchaseRecommendation(supplier_id="S", product_id="P", qty=10, unit_cost=2, expected_cost=20, eta_days=3, supplier_score=.8, reliability_score=.9, lead_time_risk=RiskLevel.LOW, risk=RiskLevel.LOW, decision_score=.85)
    assert p.expected_cost == 20
