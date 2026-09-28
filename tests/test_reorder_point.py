"""
Unit tests for I2 Reorder Point Agent — deterministic test values.

Run with: python -m pytest tests/ -v

Tests verify:
1.  Average daily demand calculation (expected_qty / horizon)
2.  Reorder point calculation (daily_demand × lead_time + safety_stock)
3.  Zero safety stock fallback (default baseline until I3 is live)
4.  Future safety-stock parameter (non-zero safety stock accepted)
5.  Inventory position calculation (available_stock + in_transit)
6.  Product below reorder point (reorder_needed = True)
7.  Product above reorder point (reorder_needed = False)
8.  Suggested reorder quantity (max(0, rop - inv_position))
9.  Never return negative reorder quantity
10. Lead time loading from suppliers.csv
11. Demand forecast loading from demand_forecasts.json
12. Forecast confidence passed through to ReorderNeed
13. Missing forecast — safe-failure (None returned, no invented values)
14. Missing supplier/lead-time — safe-failure (None returned)
15. ReorderNeed serialisation (to_dict has all required keys)
16. AgentResult generation (requires_approval=True, agent_id correct)
17. All existing I1 tests still pass (regression — covered by running test_stock_monitor.py)

Deterministic checks use exact arithmetic so expected values are obvious
without running the code.

Example calculations used in tests:
    P001 (White Bread):  expected_qty=23, horizon=7, lead_time=2 (SUP001 Bakery/Dairy)
        avg_daily = 23/7 = 3.2857...
        rop       = 3.2857 × 2 + 0 = 6.5714...
        avail=-1, in_transit=0 → inv_position=-1
        -1 <= 6.57 → reorder_needed=True
        suggested_qty = 6.57 - (-1) = 7.57... → ceil to practical order

    P004 (Maize Meal):   expected_qty=7, horizon=7, lead_time=4 (SUP002 Staples)
        avg_daily = 7/7 = 1.0
        rop       = 1.0 × 4 + 0 = 4.0
        avail=38, in_transit=2 → inv_position=40
        40 > 4 → reorder_needed=False

    P016 (Yoghurt):      expected_qty=8, horizon=7, lead_time=2 (SUP001 Bakery/Dairy)
        avg_daily = 8/7 = 1.1428...
        rop       = 1.1428 × 2 + 0 = 2.2857...
        avail=1, in_transit=0 → inv_position=1
        1 <= 2.29 → reorder_needed=True
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.services.reorder_point import ReorderPointAgent
from app.models.reorder_need import ReorderNeed
from app.models.agent_result import AgentResult
from app.models.inventory_position import InventoryPosition
from app.models.alert import StockStatus
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def agent():
    return ReorderPointAgent(data_dir=DATA_DIR)


# ------------------------------------------------------------------
# 1. Average daily demand calculation
# ------------------------------------------------------------------

class TestAverageDailyDemand:
    def test_daily_demand_basic(self, agent):
        """expected_qty=23, horizon=7 → avg_daily = 23/7"""
        forecast = agent._forecasts.get("P001")
        assert forecast is not None
        assert forecast.expected_qty == 23
        assert forecast.horizon == 7
        expected = 23 / 7
        assert forecast.daily_rate == pytest.approx(expected)

    def test_daily_demand_unity(self, agent):
        """expected_qty=7, horizon=7 → avg_daily = 1.0 exactly"""
        forecast = agent._forecasts.get("P004")
        assert forecast is not None
        assert forecast.daily_rate == pytest.approx(1.0)

    def test_daily_demand_all_products(self, agent):
        """All 20 products must have daily_rate = expected_qty / horizon."""
        for fc in agent._forecasts.values():
            expected = fc.expected_qty / fc.horizon
            assert fc.daily_rate == pytest.approx(expected), (
                f"daily_rate mismatch for {fc.product_id}"
            )


# ------------------------------------------------------------------
# 2. Reorder point calculation (pure formula)
# ------------------------------------------------------------------

class TestReorderPointFormula:
    def test_basic_rop(self):
        """rop = daily_demand × lead_time + safety_stock (default 0)"""
        rop = ReorderPointAgent.calculate_reorder_point(
            average_daily_demand=3.2857,
            lead_time_days=2,
        )
        assert rop == pytest.approx(3.2857 * 2, rel=1e-4)

    def test_rop_with_explicit_zero_safety_stock(self):
        """Explicit safety_stock=0 must equal default."""
        rop_default = ReorderPointAgent.calculate_reorder_point(5.0, 3)
        rop_explicit = ReorderPointAgent.calculate_reorder_point(5.0, 3, safety_stock=0.0)
        assert rop_default == pytest.approx(rop_explicit)

    def test_p004_rop(self, agent):
        """P004: avg_daily=1.0, lead_time=4 → rop=4.0"""
        forecast = agent._forecasts.get("P004")
        assert forecast is not None
        supplier = agent._resolve_supplier("Staples")
        assert supplier is not None
        rop = ReorderPointAgent.calculate_reorder_point(
            forecast.daily_rate, supplier.lead_time_days
        )
        assert rop == pytest.approx(4.0)

    def test_p001_rop(self, agent):
        """P001: avg_daily=23/7, lead_time=2 → rop=46/7 ≈ 6.571"""
        forecast = agent._forecasts.get("P001")
        assert forecast is not None
        supplier = agent._resolve_supplier("Bakery")
        assert supplier is not None
        rop = ReorderPointAgent.calculate_reorder_point(
            forecast.daily_rate, supplier.lead_time_days
        )
        assert rop == pytest.approx(46 / 7, rel=1e-4)


# ------------------------------------------------------------------
# 3. Zero safety stock fallback
# ------------------------------------------------------------------

class TestZeroSafetyStock:
    def test_default_safety_stock_is_zero(self):
        """Default safety_stock parameter must be 0.0."""
        rop_with_default = ReorderPointAgent.calculate_reorder_point(2.0, 5)
        rop_with_zero = ReorderPointAgent.calculate_reorder_point(2.0, 5, 0.0)
        assert rop_with_default == pytest.approx(rop_with_zero)

    def test_safety_stock_source_is_placeholder(self, agent):
        """All ReorderNeed objects must flag safety_stock_source as I3 placeholder."""
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            assert need.safety_stock == pytest.approx(0.0)
            assert need.safety_stock_source == "I3_PLACEHOLDER_ZERO"


# ------------------------------------------------------------------
# 4. Future safety-stock parameter
# ------------------------------------------------------------------

class TestFutureSafetyStock:
    def test_non_zero_safety_stock_accepted(self):
        """calculate_reorder_point must accept and use non-zero safety_stock."""
        rop = ReorderPointAgent.calculate_reorder_point(
            average_daily_demand=2.0,
            lead_time_days=3,
            safety_stock=10.0,
        )
        assert rop == pytest.approx(2.0 * 3 + 10.0)

    def test_safety_stock_increases_rop(self):
        """Adding safety stock must increase the reorder point by exactly that amount."""
        rop_zero = ReorderPointAgent.calculate_reorder_point(2.0, 3, 0.0)
        rop_ten = ReorderPointAgent.calculate_reorder_point(2.0, 3, 10.0)
        assert rop_ten - rop_zero == pytest.approx(10.0)

    def test_evaluate_product_accepts_safety_stock(self, agent):
        """evaluate_product() must propagate a non-zero safety_stock into ReorderNeed."""
        positions = agent._monitor.get_inventory_positions()
        pos = next(p for p in positions if p.product_id == "P004")
        need = agent.evaluate_product(pos, safety_stock=5.0)
        assert need is not None
        assert need.safety_stock == pytest.approx(5.0)
        # rop should be higher than with safety_stock=0
        need_zero = agent.evaluate_product(pos, safety_stock=0.0)
        assert need.reorder_point > need_zero.reorder_point


# ------------------------------------------------------------------
# 5. Inventory position calculation
# ------------------------------------------------------------------

class TestInventoryPosition:
    def test_inv_position_formula(self):
        """inventory_position = available_stock + in_transit"""
        pos = ReorderPointAgent.calculate_inventory_position(
            available_stock=10.0, in_transit=5.0
        )
        assert pos == pytest.approx(15.0)

    def test_inv_position_negative_available(self):
        """Negative available_stock (e.g. damaged > on_hand) still adds in_transit."""
        pos = ReorderPointAgent.calculate_inventory_position(
            available_stock=-1.0, in_transit=0.0
        )
        assert pos == pytest.approx(-1.0)

    def test_inv_position_zero(self):
        assert ReorderPointAgent.calculate_inventory_position(0.0, 0.0) == pytest.approx(0.0)

    def test_p001_inv_position(self, agent):
        """P001: available_stock=-1, in_transit=0 → inv_position=-1"""
        need = agent.get_decision_for_product("P001")
        assert need is not None
        assert need["inventory_position"] == pytest.approx(-1.0)


# ------------------------------------------------------------------
# 6. Product below reorder point
# ------------------------------------------------------------------

class TestBelowReorderPoint:
    def test_p001_reorder_needed(self, agent):
        """P001 (out of stock) must have reorder_needed=True."""
        need = agent.get_decision_for_product("P001")
        assert need is not None
        assert need["reorder_needed"] is True

    def test_p001_inv_below_rop(self, agent):
        """P001: inv_position=-1, rop≈6.57 → inv_position < rop."""
        need = agent.get_decision_for_product("P001")
        assert need is not None
        assert need["inventory_position"] < need["reorder_point"]

    def test_p016_reorder_needed(self, agent):
        """P016 (Yoghurt, available=1, in_transit=0): inv_position=1 ≤ rop≈2.29."""
        need = agent.get_decision_for_product("P016")
        assert need is not None
        assert need["reorder_needed"] is True
        assert need["inventory_position"] <= need["reorder_point"]


# ------------------------------------------------------------------
# 7. Product above reorder point
# ------------------------------------------------------------------

class TestAboveReorderPoint:
    def test_p004_no_reorder(self, agent):
        """P004 (Maize Meal, available=38, in_transit=2): inv_position=40 >> rop=4.0."""
        need = agent.get_decision_for_product("P004")
        assert need is not None
        assert need["reorder_needed"] is False
        assert need["inventory_position"] > need["reorder_point"]

    def test_p010_no_reorder(self, agent):
        """P010 (Soft Drink, available=56, in_transit=4): healthy stock, no reorder."""
        need = agent.get_decision_for_product("P010")
        assert need is not None
        assert need["reorder_needed"] is False

    def test_p020_no_reorder(self, agent):
        """P020 (Bottled Water, available=68): healthy stock, no reorder."""
        need = agent.get_decision_for_product("P020")
        assert need is not None
        assert need["reorder_needed"] is False


# ------------------------------------------------------------------
# 8. Suggested reorder quantity
# ------------------------------------------------------------------

class TestSuggestedReorderQty:
    def test_suggested_qty_above_zero_when_reorder_needed(self, agent):
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            if need.reorder_needed:
                assert need.suggested_reorder_qty > 0, (
                    f"{need.product_id} has reorder_needed=True but suggested_qty=0"
                )

    def test_suggested_qty_zero_when_no_reorder(self, agent):
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            if not need.reorder_needed:
                assert need.suggested_reorder_qty == pytest.approx(0.0)

    def test_suggested_qty_formula(self):
        """suggested = max(0, rop - inv_position) — deterministic check."""
        qty = ReorderPointAgent.calculate_suggested_qty(
            reorder_point=10.0, inventory_position=4.0
        )
        assert qty == pytest.approx(6.0)

    def test_p001_suggested_qty(self, agent):
        """P001: rop≈6.57, inv_position=-1 → suggested≈7.57 (rounded to 2dp in dict)."""
        need = agent.get_decision_for_product("P001")
        assert need is not None
        # to_dict() rounds values to 2dp; compare rounded expected against rounded actual
        raw_expected = need["reorder_point"] - need["inventory_position"]
        assert need["suggested_reorder_qty"] == pytest.approx(round(raw_expected, 2), rel=1e-4)


# ------------------------------------------------------------------
# 9. Never return negative reorder quantity
# ------------------------------------------------------------------

class TestNeverNegativeQty:
    def test_calculate_suggested_qty_never_negative(self):
        """Even if inv_position > rop, suggested_qty must be 0, not negative."""
        qty = ReorderPointAgent.calculate_suggested_qty(
            reorder_point=5.0, inventory_position=100.0
        )
        assert qty == pytest.approx(0.0)

    def test_all_suggested_qty_non_negative(self, agent):
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            assert need.suggested_reorder_qty >= 0.0, (
                f"{need.product_id} returned negative suggested_reorder_qty"
            )


# ------------------------------------------------------------------
# 10. Lead time loading
# ------------------------------------------------------------------

class TestLeadTimeLoading:
    def test_suppliers_loaded(self, agent):
        assert len(agent._suppliers) == 5

    def test_sup001_lead_time(self, agent):
        sup = agent._suppliers.get("SUP001")
        assert sup is not None
        assert sup.lead_time_days == 2

    def test_sup004_lead_time(self, agent):
        """HomeCare Wholesale has the longest lead time (5 days)."""
        sup = agent._suppliers.get("SUP004")
        assert sup is not None
        assert sup.lead_time_days == 5

    def test_supplier_lookup_bakery(self, agent):
        sup = agent._resolve_supplier("Bakery")
        assert sup is not None
        assert sup.lead_time_days == 2   # SUP001

    def test_supplier_lookup_frozen(self, agent):
        sup = agent._resolve_supplier("Frozen")
        assert sup is not None
        assert sup.lead_time_days == 4   # SUP005

    def test_supplier_lookup_household(self, agent):
        sup = agent._resolve_supplier("Household")
        assert sup is not None
        assert sup.lead_time_days == 5   # SUP004

    def test_supplier_fallback_unknown_category(self, agent):
        """Unknown category falls back to max lead time supplier."""
        sup = agent._resolve_supplier("UNKNOWN_CATEGORY_XYZ")
        assert sup is not None   # fallback must always return something


# ------------------------------------------------------------------
# 11. Demand forecast loading
# ------------------------------------------------------------------

class TestDemandForecastLoading:
    def test_all_forecasts_loaded(self, agent):
        assert len(agent._forecasts) == 20

    def test_p001_forecast(self, agent):
        fc = agent._forecasts.get("P001")
        assert fc is not None
        assert fc.expected_qty == 23
        assert fc.horizon == 7

    def test_p020_forecast(self, agent):
        fc = agent._forecasts.get("P020")
        assert fc is not None
        assert fc.expected_qty == 20


# ------------------------------------------------------------------
# 12. Forecast confidence passed through
# ------------------------------------------------------------------

class TestForecastConfidence:
    def test_confidence_in_reorder_need(self, agent):
        """forecast_confidence in ReorderNeed must match demand_forecasts.json."""
        decisions = agent.evaluate_all()
        forecasts = agent._forecasts
        for need, _ in decisions:
            fc = forecasts.get(need.product_id)
            if fc:
                assert need.forecast_confidence == pytest.approx(fc.confidence)

    def test_p001_confidence(self, agent):
        need = agent.get_decision_for_product("P001")
        assert need is not None
        assert need["forecast_confidence"] == pytest.approx(0.82)


# ------------------------------------------------------------------
# 13. Missing forecast — safe-failure
# ------------------------------------------------------------------

class TestMissingForecast:
    def test_evaluate_product_returns_none_without_forecast(self, agent):
        """
        If forecast is missing, evaluate_product must return None — not invent values.
        Simulate by temporarily removing a forecast.
        """
        from app.models.inventory_position import InventoryPosition
        from app.models.alert import StockStatus

        # Build a fake position for a product that won't have a forecast
        fake_pos = InventoryPosition(
            product_id="P_FAKE_NO_FORECAST",
            sku="SKU-FAKE",
            product_name="Fake Product",
            category="Bakery",
            store_id="STORE-001",
            snapshot_timestamp=datetime.now(),
            stock_on_hand=10.0,
            reserved=0.0,
            damaged=0.0,
            in_transit=0.0,
            available_stock=10.0,
            stock_status=StockStatus.HEALTHY,
            days_of_supply=5.0,
            needs_attention=False,
            forecast_7d_demand=0.0,
            forecast_confidence=0.0,
            forecast_source="none",
        )
        result = agent.evaluate_product(fake_pos)
        assert result is None, "evaluate_product must return None when forecast is missing"


# ------------------------------------------------------------------
# 14. Missing supplier / lead-time — safe-failure
# ------------------------------------------------------------------

class TestMissingSupplier:
    def test_resolve_supplier_with_empty_suppliers(self, agent):
        """
        If suppliers dict were empty, resolve_supplier must return None.
        Test by calling with saved suppliers and patching temporarily.
        """
        saved = agent._suppliers
        agent._suppliers = {}
        result = agent._resolve_supplier("Bakery")
        agent._suppliers = saved
        assert result is None, "resolve_supplier must return None when no suppliers loaded"

    def test_evaluate_product_returns_none_without_supplier(self, agent):
        """
        If suppliers are empty, evaluate_product must return None.
        """
        from app.models.inventory_position import InventoryPosition
        from app.models.alert import StockStatus

        pos = next(iter(agent._monitor.get_inventory_positions()))
        saved = agent._suppliers
        agent._suppliers = {}
        result = agent.evaluate_product(pos)
        agent._suppliers = saved
        assert result is None, "evaluate_product must return None when supplier is missing"


# ------------------------------------------------------------------
# 15. ReorderNeed serialisation
# ------------------------------------------------------------------

class TestReorderNeedSerialisation:
    REQUIRED_KEYS = {
        "product_id", "sku", "product_name", "category", "store_id",
        "available_stock", "in_transit", "inventory_position",
        "average_daily_demand", "demand_forecast", "forecast_horizon",
        "forecast_confidence",
        "supplier_id", "supplier_name", "lead_time_days",
        "safety_stock", "safety_stock_source",
        "reorder_point",
        "reorder_needed", "suggested_reorder_qty",
        "reason", "generated_at",
    }

    def test_to_dict_has_all_required_keys(self, agent):
        decisions = agent.evaluate_all()
        assert len(decisions) > 0
        for need, _ in decisions:
            d = need.to_dict()
            missing = self.REQUIRED_KEYS - set(d.keys())
            assert not missing, f"Missing keys in ReorderNeed.to_dict(): {missing}"

    def test_all_values_json_serialisable(self, agent):
        """All values in to_dict() must be JSON-serialisable types."""
        import json
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            try:
                json.dumps(need.to_dict())
            except (TypeError, ValueError) as exc:
                pytest.fail(f"ReorderNeed.to_dict() not JSON-serialisable: {exc}")

    def test_no_reorder_qty_field_leaks(self, agent):
        """The dict must not expose I3/Procurement fields like reorder_qty."""
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            d = need.to_dict()
            # suggested_reorder_qty is fine; 'reorder_qty' alone is not expected
            assert "reorder_qty" not in d


# ------------------------------------------------------------------
# 16. AgentResult generation
# ------------------------------------------------------------------

class TestAgentResult:
    def test_agent_result_produced_for_every_decision(self, agent):
        decisions = agent.evaluate_all()
        assert len(decisions) > 0
        for need, ar in decisions:
            assert isinstance(ar, AgentResult)

    def test_agent_id_is_i2(self, agent):
        decisions = agent.evaluate_all()
        for _, ar in decisions:
            assert ar.agent_id == "I2_REORDER_POINT"

    def test_requires_approval_always_true(self, agent):
        """I2 must never auto-execute. requires_approval must always be True."""
        decisions = agent.evaluate_all()
        for _, ar in decisions:
            assert ar.requires_approval is True

    def test_action_type_reorder_when_needed(self, agent):
        decisions = agent.evaluate_all()
        for need, ar in decisions:
            if need.reorder_needed:
                assert ar.action_type == "REORDER"
                assert ar.action == "PLACE_REORDER"
            else:
                assert ar.action_type == "NO_ACTION"
                assert ar.action == "HOLD"

    def test_agent_result_confidence_range(self, agent):
        decisions = agent.evaluate_all()
        for _, ar in decisions:
            assert 0.0 <= ar.confidence <= 1.0

    def test_agent_result_to_dict_has_required_keys(self, agent):
        required = {
            "recommendation_id", "agent_id", "entity_type", "entity_id",
            "action_type", "action", "rationale", "evidence_refs",
            "confidence", "risk_level", "requires_approval",
            "model_or_rule_version", "generated_at", "expires_at",
        }
        decisions = agent.evaluate_all()
        for _, ar in decisions:
            d = ar.to_dict()
            missing = required - set(d.keys())
            assert not missing, f"Missing AgentResult keys: {missing}"

    def test_evidence_refs_include_data_sources(self, agent):
        decisions = agent.evaluate_all()
        for need, ar in decisions:
            refs = ar.evidence_refs
            assert any("inventory_snapshots" in r for r in refs)
            assert any("demand_forecasts" in r for r in refs)
            assert any("suppliers" in r for r in refs)


# ------------------------------------------------------------------
# 17. End-to-end — all products evaluated
# ------------------------------------------------------------------

class TestEndToEnd:
    def test_all_products_evaluated(self, agent):
        """get_reorder_decisions() must return a decision for all 20 products."""
        decisions = agent.get_reorder_decisions()
        assert len(decisions) == 20

    def test_insufficient_data_list_is_empty(self, agent):
        """With full dataset, no products should have insufficient data."""
        missing = agent.get_insufficient_data_products()
        assert len(missing) == 0, (
            f"Unexpected insufficient-data products: "
            f"{[m['product_id'] for m in missing]}"
        )

    def test_urgent_reorders_are_subset(self, agent):
        """get_urgent_reorders() must be a subset of get_reorder_decisions()."""
        all_decisions = agent.get_reorder_decisions()
        urgent = agent.get_urgent_reorders()
        all_pids = {d["product_id"] for d in all_decisions}
        urgent_pids = {d["product_id"] for d in urgent}
        assert urgent_pids.issubset(all_pids)

    def test_urgent_all_reorder_needed(self, agent):
        urgent = agent.get_urgent_reorders()
        for d in urgent:
            assert d["reorder_needed"] is True

    def test_p001_urgent_reorder(self, agent):
        """P001 (out of stock) must appear in urgent reorders."""
        urgent = agent.get_urgent_reorders()
        pids = [d["product_id"] for d in urgent]
        assert "P001" in pids

    def test_p004_not_urgent(self, agent):
        """P004 (healthy, rop=4, inv_position=40) must NOT appear in urgent reorders."""
        urgent = agent.get_urgent_reorders()
        pids = [d["product_id"] for d in urgent]
        assert "P004" not in pids

    def test_reason_contains_actual_values(self, agent):
        """Every reason string must include numeric values, not placeholders."""
        decisions = agent.evaluate_all()
        for need, _ in decisions:
            reason = need.reason
            assert "units" in reason.lower(), (
                f"Reason for {need.product_id} does not mention 'units': {reason}"
            )
            # Should contain at least one number
            assert any(c.isdigit() for c in reason), (
                f"Reason for {need.product_id} contains no numbers: {reason}"
            )
