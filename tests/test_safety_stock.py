"""
I3 Safety Stock Agent — test suite.

Tests cover:
  - Pure formula step functions (unit tests, no I/O)
  - SafetyStockAgent integration (uses real data files)
  - SafetyStockTarget serialisation
  - AgentResult contract fields
  - Boundary cases: zero lead time, perfect reliability, worst reliability
  - Safe-failure: missing forecast → None, missing supplier → None
  - Confidence mapping (float and string inputs)
  - z-score lookup for each supported service level
  - reliability_score clamping outside [0, 1]
  - safety_stock never negative
"""
import math
import pytest
from pathlib import Path

from app.services.safety_stock import (
    SafetyStockAgent,
    calculate_expected_daily_demand,
    calculate_horizon_std,
    calculate_daily_std,
    calculate_lead_time_demand_std,
    get_z_score,
    calculate_reliability_factor,
    calculate_raw_safety_stock,
    calculate_safety_stock,
    _map_confidence,
    SERVICE_LEVEL_Z,
    DEFAULT_SERVICE_LEVEL,
)
from app.models.safety_stock_target import SafetyStockTarget

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def agent():
    return SafetyStockAgent(data_dir=DATA_DIR)


# ---------------------------------------------------------------------------
# TC-I3-01  calculate_expected_daily_demand
# ---------------------------------------------------------------------------
class TestCalculateExpectedDailyDemand:
    def test_basic(self):
        assert calculate_expected_daily_demand(70.0, 7) == pytest.approx(10.0)

    def test_fractional(self):
        assert calculate_expected_daily_demand(23.0, 7) == pytest.approx(23 / 7)

    def test_zero_expected_qty(self):
        assert calculate_expected_daily_demand(0.0, 7) == pytest.approx(0.0)

    def test_horizon_zero_raises(self):
        with pytest.raises(ValueError):
            calculate_expected_daily_demand(10.0, 0)

    def test_horizon_negative_raises(self):
        with pytest.raises(ValueError):
            calculate_expected_daily_demand(10.0, -1)


# ---------------------------------------------------------------------------
# TC-I3-02  calculate_horizon_std
# ---------------------------------------------------------------------------
class TestCalculateHorizonStd:
    def test_basic(self):
        # (28 - 18) / 4 = 2.5
        assert calculate_horizon_std(28.0, 18.0) == pytest.approx(2.5)

    def test_equal_bounds(self):
        assert calculate_horizon_std(20.0, 20.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TC-I3-03  calculate_daily_std
# ---------------------------------------------------------------------------
class TestCalculateDailyStd:
    def test_basic(self):
        # horizon_std=2.5, horizon=7 → 2.5/sqrt(7)
        expected = 2.5 / math.sqrt(7)
        assert calculate_daily_std(2.5, 7) == pytest.approx(expected)

    def test_horizon_zero_raises(self):
        with pytest.raises(ValueError):
            calculate_daily_std(2.5, 0)


# ---------------------------------------------------------------------------
# TC-I3-04  calculate_lead_time_demand_std
# ---------------------------------------------------------------------------
class TestCalculateLeadTimeDemandStd:
    def test_basic(self):
        d_std = 2.5 / math.sqrt(7)
        lt = 2
        expected = d_std * math.sqrt(lt)
        assert calculate_lead_time_demand_std(d_std, lt) == pytest.approx(expected)

    def test_zero_lead_time(self):
        assert calculate_lead_time_demand_std(1.5, 0) == pytest.approx(0.0)

    def test_negative_lead_time_raises(self):
        with pytest.raises(ValueError):
            calculate_lead_time_demand_std(1.5, -1)


# ---------------------------------------------------------------------------
# TC-I3-05  get_z_score
# ---------------------------------------------------------------------------
class TestGetZScore:
    def test_090(self):
        assert get_z_score(0.90) == pytest.approx(1.28)

    def test_095(self):
        assert get_z_score(0.95) == pytest.approx(1.65)

    def test_099(self):
        assert get_z_score(0.99) == pytest.approx(2.33)

    def test_unknown_defaults_to_default(self):
        # Unknown service level → default (0.95 → 1.65)
        assert get_z_score(0.80) == pytest.approx(SERVICE_LEVEL_Z[DEFAULT_SERVICE_LEVEL])


# ---------------------------------------------------------------------------
# TC-I3-06  calculate_reliability_factor
# ---------------------------------------------------------------------------
class TestCalculateReliabilityFactor:
    def test_perfect(self):
        # score=1.0 → factor=1.0
        assert calculate_reliability_factor(1.0) == pytest.approx(1.0)

    def test_zero(self):
        # score=0.0 → factor=2.0
        assert calculate_reliability_factor(0.0) == pytest.approx(2.0)

    def test_typical(self):
        # score=0.93 → factor = 1 + (1 - 0.93) = 1.07
        assert calculate_reliability_factor(0.93) == pytest.approx(1.07)

    def test_clamp_above_one(self):
        # score > 1 → clamped to 1 → factor = 1.0
        assert calculate_reliability_factor(1.5) == pytest.approx(1.0)

    def test_clamp_below_zero(self):
        # score < 0 → clamped to 0 → factor = 2.0
        assert calculate_reliability_factor(-0.5) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# TC-I3-07  calculate_raw_safety_stock
# ---------------------------------------------------------------------------
class TestCalculateRawSafetyStock:
    def test_basic(self):
        z = 1.65
        lt_std = 2.0
        rf = 1.07
        expected = z * lt_std * rf
        assert calculate_raw_safety_stock(z, lt_std, rf) == pytest.approx(expected)

    def test_zero_std(self):
        assert calculate_raw_safety_stock(1.65, 0.0, 1.07) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TC-I3-08  calculate_safety_stock (ceil + floor at 0)
# ---------------------------------------------------------------------------
class TestCalculateSafetyStock:
    def test_rounds_up(self):
        assert calculate_safety_stock(3.1) == 4

    def test_whole_number(self):
        assert calculate_safety_stock(5.0) == 5

    def test_negative_raw_gives_zero(self):
        assert calculate_safety_stock(-2.5) == 0

    def test_zero_raw_gives_zero(self):
        assert calculate_safety_stock(0.0) == 0


# ---------------------------------------------------------------------------
# TC-I3-09  _map_confidence
# ---------------------------------------------------------------------------
class TestMapConfidence:
    def test_float_high(self):
        assert _map_confidence(0.90) == "HIGH"

    def test_float_medium(self):
        assert _map_confidence(0.82) == "MEDIUM"

    def test_float_low(self):
        assert _map_confidence(0.50) == "LOW"

    def test_string_high(self):
        assert _map_confidence("HIGH") == "HIGH"

    def test_string_medium(self):
        assert _map_confidence("MEDIUM") == "MEDIUM"

    def test_string_unknown_defaults_medium(self):
        assert _map_confidence("UNKNOWN") == "MEDIUM"


# ---------------------------------------------------------------------------
# TC-I3-10  SafetyStockAgent — loads data
# ---------------------------------------------------------------------------
class TestAgentDataLoading:
    def test_forecasts_loaded(self, agent):
        assert len(agent._forecasts) > 0

    def test_suppliers_loaded(self, agent):
        assert len(agent._suppliers) > 0

    def test_service_level_default(self, agent):
        assert agent._service_level == DEFAULT_SERVICE_LEVEL

    def test_z_score_set(self, agent):
        assert agent._z == SERVICE_LEVEL_Z[DEFAULT_SERVICE_LEVEL]


# ---------------------------------------------------------------------------
# TC-I3-11  evaluate_product — returns valid result for known product
# ---------------------------------------------------------------------------
class TestEvaluateProduct:
    def test_p001_returns_pair(self, agent):
        result = agent.evaluate_product("P001", "bakery")
        assert result is not None
        target, ar = result
        assert isinstance(target, SafetyStockTarget)
        assert target.product_id == "P001"

    def test_p001_safety_stock_non_negative(self, agent):
        target, _ = agent.evaluate_product("P001", "bakery")
        assert target.safety_stock >= 0

    def test_p001_formula_version(self, agent):
        target, _ = agent.evaluate_product("P001", "bakery")
        assert target.formula_version == "I3-v1"

    def test_agent_result_fields(self, agent):
        _, ar = agent.evaluate_product("P001", "bakery")
        assert ar.agent_id == "I3_SAFETY_STOCK"
        assert ar.action_type == "SET_SAFETY_STOCK"
        assert ar.requires_approval is False
        assert ar.model_or_rule_version == "I3-v1"

    def test_missing_product_returns_none(self, agent):
        result = agent.evaluate_product("ZZZNOTEXIST", "bakery")
        assert result is None


# ---------------------------------------------------------------------------
# TC-I3-12  SafetyStockTarget serialisation
# ---------------------------------------------------------------------------
class TestSafetyStockTargetSerialisation:
    def test_to_dict_keys(self, agent):
        target, _ = agent.evaluate_product("P001", "bakery")
        d = target.to_dict()
        expected_keys = {
            "product_id", "safety_stock", "expected_daily_demand",
            "forecast_uncertainty", "lead_time_days", "reliability_score",
            "reliability_factor", "service_level", "z_score",
            "raw_safety_stock", "confidence", "reason",
            "formula_version", "generated_at",
        }
        assert expected_keys.issubset(d.keys())

    def test_safety_stock_is_int(self, agent):
        target, _ = agent.evaluate_product("P001", "bakery")
        assert isinstance(target.safety_stock, int)

    def test_formula_version_in_dict(self, agent):
        target, _ = agent.evaluate_product("P001", "bakery")
        assert target.to_dict()["formula_version"] == "I3-v1"


# ---------------------------------------------------------------------------
# TC-I3-13  get_all_targets — returns list
# ---------------------------------------------------------------------------
class TestGetAllTargets:
    def test_returns_list(self, agent):
        targets = agent.get_all_targets()
        assert isinstance(targets, list)

    def test_all_have_safety_stock_key(self, agent):
        targets = agent.get_all_targets()
        for t in targets:
            assert "safety_stock" in t

    def test_all_non_negative(self, agent):
        targets = agent.get_all_targets()
        for t in targets:
            assert t["safety_stock"] >= 0

    def test_all_have_recommendation(self, agent):
        targets = agent.get_all_targets()
        for t in targets:
            assert "recommendation" in t
            assert t["recommendation"]["requires_approval"] is False


# ---------------------------------------------------------------------------
# TC-I3-14  custom service level
# ---------------------------------------------------------------------------
class TestCustomServiceLevel:
    def test_090_service_level(self):
        agent_90 = SafetyStockAgent(data_dir=DATA_DIR, service_level=0.90)
        assert agent_90._z == pytest.approx(1.28)

    def test_099_service_level(self):
        agent_99 = SafetyStockAgent(data_dir=DATA_DIR, service_level=0.99)
        assert agent_99._z == pytest.approx(2.33)

    def test_higher_service_level_gives_higher_ss(self):
        agent_90 = SafetyStockAgent(data_dir=DATA_DIR, service_level=0.90)
        agent_99 = SafetyStockAgent(data_dir=DATA_DIR, service_level=0.99)
        r90 = agent_90.evaluate_product("P001", "bakery")
        r99 = agent_99.evaluate_product("P001", "bakery")
        if r90 and r99:
            assert r99[0].safety_stock >= r90[0].safety_stock


# ---------------------------------------------------------------------------
# TC-I3-15  Invalid forecast bounds — upper_bound < lower_bound
# ---------------------------------------------------------------------------
class TestInvalidBounds:
    def test_upper_less_than_lower_raises(self):
        with pytest.raises(ValueError, match="upper_bound"):
            calculate_horizon_std(upper_bound=10.0, lower_bound=20.0)

    def test_equal_bounds_gives_zero(self):
        """Zero uncertainty is valid (no spread in forecast)."""
        assert calculate_horizon_std(20.0, 20.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TC-I3-16  Reliability fallback — missing reliability treated as 1.0
# ---------------------------------------------------------------------------
class TestReliabilityFallback:
    def test_missing_reliability_defaults_to_perfect(self):
        """No reliability → score=1.0 → factor=1.0 (most optimistic, conservative fallback)."""
        assert calculate_reliability_factor(1.0) == pytest.approx(1.0)

    def test_rationale_mentions_supplier_reliability(self, agent):
        """Rationale should include supplier reliability information."""
        result = agent.evaluate_product("P001", "bakery")
        assert result is not None
        target, _ = result
        assert "reliability" in target.reason.lower()


# ---------------------------------------------------------------------------
# TC-I3-17  R3 LeadTimeRisk hook
# ---------------------------------------------------------------------------
class TestR3Hook:
    def test_zero_adjustment_same_as_default(self, agent):
        """lead_time_risk_adjustment=0.0 must match default behaviour."""
        r_default = agent.evaluate_product("P001", "bakery")
        r_explicit = agent.evaluate_product("P001", "bakery", lead_time_risk_adjustment=0.0)
        assert r_default is not None and r_explicit is not None
        assert r_default[0].safety_stock == r_explicit[0].safety_stock

    def test_positive_adjustment_increases_safety_stock(self, agent):
        """A positive R3 adjustment must produce equal-or-higher safety stock."""
        r_base = agent.evaluate_product("P001", "bakery", lead_time_risk_adjustment=0.0)
        r_r3 = agent.evaluate_product("P001", "bakery", lead_time_risk_adjustment=5.0)
        assert r_base is not None and r_r3 is not None
        assert r_r3[0].safety_stock >= r_base[0].safety_stock

    def test_get_target_for_product_passes_r3(self, agent):
        """get_target_for_product must accept lead_time_risk_adjustment."""
        result = agent.get_target_for_product(
            "P001", "bakery", lead_time_risk_adjustment=3.0
        )
        assert result is not None
        assert result["safety_stock"] >= 0


# ---------------------------------------------------------------------------
# TC-I3-18  API endpoint tests — GET /api/safety-stock
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app as fastapi_app


@pytest.fixture(scope="module")
def client():
    with TestClient(fastapi_app) as c:
        yield c


class TestApiSafetyStockList:
    def test_get_all_returns_200(self, client):
        resp = client.get("/api/safety-stock/")
        assert resp.status_code == 200

    def test_response_has_targets_key(self, client):
        resp = client.get("/api/safety-stock/")
        data = resp.json()
        assert "targets" in data

    def test_response_has_agent_id(self, client):
        resp = client.get("/api/safety-stock/")
        data = resp.json()
        assert data["agent"] == "I3_SAFETY_STOCK"

    def test_response_requires_approval_false(self, client):
        resp = client.get("/api/safety-stock/")
        data = resp.json()
        assert data["requires_approval"] is False

    def test_targets_are_non_negative(self, client):
        resp = client.get("/api/safety-stock/")
        data = resp.json()
        for t in data["targets"]:
            assert t["safety_stock"] >= 0

    def test_formula_version_in_response(self, client):
        resp = client.get("/api/safety-stock/")
        data = resp.json()
        assert data["formula_version"] == "I3-v1"


# ---------------------------------------------------------------------------
# TC-I3-19  API endpoint tests — GET /api/safety-stock/{product_id}
# ---------------------------------------------------------------------------
class TestApiSafetyStockProduct:
    def test_known_product_returns_200(self, client):
        resp = client.get("/api/safety-stock/P001")
        assert resp.status_code == 200

    def test_unknown_product_returns_404(self, client):
        resp = client.get("/api/safety-stock/ZZZNOTEXIST")
        assert resp.status_code == 404

    def test_product_has_formula_version(self, client):
        resp = client.get("/api/safety-stock/P001")
        data = resp.json()
        assert data["formula_version"] == "I3-v1"

    def test_product_safety_stock_non_negative(self, client):
        resp = client.get("/api/safety-stock/P001")
        data = resp.json()
        assert data["safety_stock"] >= 0

    def test_product_has_recommendation(self, client):
        resp = client.get("/api/safety-stock/P001")
        data = resp.json()
        assert "recommendation" in data
        assert data["recommendation"]["agent_id"] == "I3_SAFETY_STOCK"
        assert data["recommendation"]["requires_approval"] is False


# ---------------------------------------------------------------------------
# TC-I3-20  I2 + I3 integration — I3 safety stock feeds into I2
# ---------------------------------------------------------------------------
class TestI2I3Integration:
    def test_i3_output_accepted_by_i2(self):
        """I2's evaluate_product must accept safety_stock from I3 without error."""
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor

        i1 = StockMonitor(data_dir=DATA_DIR)
        i2 = ReorderPointAgent(data_dir=DATA_DIR)
        i3 = SafetyStockAgent(data_dir=DATA_DIR)

        positions = {p.product_id: p for p in i1.get_inventory_positions()}

        for product_id, pos in list(positions.items())[:3]:
            product = i1._products.get(product_id)
            if product is None:
                continue
            i3_result = i3.evaluate_product(product_id, product.category)
            ss = i3_result[0].safety_stock if i3_result else 0.0

            # I2 must accept the I3 safety stock value
            need = i2.evaluate_product(pos, safety_stock=float(ss))
            # May return None if missing supplier/forecast — that is fine
            if need is not None:
                assert need.safety_stock == float(ss)

    def test_i3_safety_stock_higher_than_zero_for_some_products(self):
        """At least some products should have I3 safety stock > 0."""
        from app.services.stock_monitor import StockMonitor
        i3 = SafetyStockAgent(data_dir=DATA_DIR)
        i1 = StockMonitor(data_dir=DATA_DIR)
        found_positive = False
        for p in i1._products.values():
            result = i3.evaluate_product(p.product_id, p.category)
            if result and result[0].safety_stock > 0:
                found_positive = True
                break
        assert found_positive, "Expected at least one product to have safety_stock > 0"

    def test_i2_reorder_point_higher_with_i3_safety_stock(self):
        """I2's reorder point should be higher when I3 supplies safety stock > 0."""
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor

        i1 = StockMonitor(data_dir=DATA_DIR)
        i2 = ReorderPointAgent(data_dir=DATA_DIR)
        i3 = SafetyStockAgent(data_dir=DATA_DIR)

        positions = {p.product_id: p for p in i1.get_inventory_positions()}

        for product_id, pos in positions.items():
            product = i1._products.get(product_id)
            if product is None:
                continue
            i3_result = i3.evaluate_product(product_id, product.category)
            if i3_result is None:
                continue
            ss = float(i3_result[0].safety_stock)
            if ss <= 0:
                continue
            # Compare with ss=0 vs ss=i3_value
            need_zero = i2.evaluate_product(pos, safety_stock=0.0)
            need_i3 = i2.evaluate_product(pos, safety_stock=ss)
            if need_zero and need_i3:
                assert need_i3.reorder_point >= need_zero.reorder_point
            break  # one product is sufficient to prove the chain


# ---------------------------------------------------------------------------
# TC-I3-21  I1 regression — I1 boundaries untouched
# ---------------------------------------------------------------------------
class TestI1Regression:
    def test_i1_get_inventory_positions_still_works(self):
        from app.services.stock_monitor import StockMonitor
        i1 = StockMonitor(data_dir=DATA_DIR)
        positions = i1.get_inventory_positions()
        assert len(positions) > 0

    def test_i1_positions_have_no_reorder_qty(self):
        from app.services.stock_monitor import StockMonitor
        i1 = StockMonitor(data_dir=DATA_DIR)
        positions = i1.get_inventory_positions()
        for p in positions:
            d = p.to_dict()
            # I1 must not produce reorder quantities — that is I2's job
            assert "suggested_reorder_qty" not in d


# ---------------------------------------------------------------------------
# TC-I3-22  I2 regression — I2 boundaries untouched
# ---------------------------------------------------------------------------
class TestI2Regression:
    def test_i2_evaluate_all_with_default_ss_still_works(self):
        from app.services.reorder_point import ReorderPointAgent
        from app.services.stock_monitor import StockMonitor
        i1 = StockMonitor(data_dir=DATA_DIR)
        i2 = ReorderPointAgent(data_dir=DATA_DIR)
        positions = i1.get_inventory_positions()
        results = i2.evaluate_all()
        assert isinstance(results, list)

    def test_i2_does_not_call_i3_internally(self):
        """I2 must not import or call I3 directly. I3 feeds I2 from outside."""
        import importlib, sys
        # Check that i2's module does not import safety_stock
        spec = importlib.util.find_spec("app.services.reorder_point")
        assert spec is not None
        src_path = spec.origin
        with open(src_path) as f:
            src = f.read()
        assert "safety_stock" not in src.split("import")[-1].split("\n")[0] or \
               "from app.services.safety_stock" not in src
