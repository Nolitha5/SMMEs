"""
I2 Reorder Point Agent — core business logic.

I2 is responsible for:
  - Consuming InventoryPosition objects produced by I1
  - Reading demand forecasts from demand_forecasts.json (read-only)
  - Reading supplier lead times from suppliers.csv (category-to-supplier lookup)
  - Applying the deterministic reorder-point formula:
        reorder_point = average_daily_demand × lead_time_days + safety_stock
  - Comparing each product's inventory_position against the reorder_point
  - Producing ReorderNeed objects (the I2 output contract)
  - Wrapping each reorder recommendation in an AgentResult

I2 is NOT responsible for:
  - Stock monitoring or available_stock calculation  → I1
  - Demand forecasting                              → D4 (Demand Sensing)
  - Safety-stock modelling                          → I3 (not yet implemented)
  - Expiry / slow-stock analysis                    → I4
  - Inventory anomaly detection                     → I5
  - Supplier selection                              → Procurement domain
  - Executing purchases                             → Procurement / human approval

Safety stock:
  safety_stock = 0 as a temporary baseline.
  When I3 is implemented, pass its output via the `safety_stock` parameter
  of `calculate_reorder_point()` — no other change is required.

Supplier mapping:
  suppliers.csv contains category-based suppliers, not product-specific ones.
  I2 resolves the supplier for a product by matching the product's category
  against supplier category strings (case-insensitive, substring match).
  If no match is found, the supplier with the longest lead time (most
  conservative) is used as a safe fallback.
  Supplier selection belongs to the Procurement domain; this lookup is
  a temporary placeholder until a product-supplier mapping is available.

No LLM, no external APIs, no database — fully offline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.agent_result import AgentResult
from app.models.demand_forecast import DemandForecast
from app.models.inventory_position import InventoryPosition
from app.models.reorder_need import ReorderNeed
from app.models.supplier import Supplier
from app.services.data_loader import DataLoader
from app.services.stock_monitor import StockMonitor

# I2 identification
AGENT_ID = "I2_REORDER_POINT"
RULE_VERSION = "I2-v1.0-basic-rop"

# Safety stock placeholder label — replaced when I3 is implemented
SAFETY_STOCK_SOURCE_PLACEHOLDER = "I3_PLACEHOLDER_ZERO"

# Category keywords → supplier category strings (lowercase)
# Supplier category field in suppliers.csv uses "/" to separate categories
CATEGORY_SUPPLIER_MAP: Dict[str, str] = {
    "bakery":           "bakery",
    "dairy":            "bakery",        # SUP001 covers Bakery/Dairy
    "staples":          "staples",
    "canned goods":     "staples",       # SUP002 covers Staples/Canned
    "condiments":       "staples",
    "spreads":          "staples",
    "breakfast":        "staples",
    "beverages":        "beverages",
    "snacks":           "beverages",     # SUP003 covers Beverages/Snacks
    "confectionery":    "beverages",
    "household":        "household",
    "frozen":           "frozen",
}


class ReorderPointAgent:
    """
    I2 Reorder Point Agent.

    Consumes I1's StockMonitor (for InventoryPosition objects) and the
    shared DataLoader (for suppliers). Produces ReorderNeed decisions
    and AgentResult wrappers.
    """

    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._loader = DataLoader(data_dir)
        self._monitor = StockMonitor(data_dir)
        self._suppliers: Dict[str, Supplier] = {}
        self._forecasts: Dict[str, DemandForecast] = {}
        self._reload()

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _reload(self):
        self._suppliers = self._loader.load_suppliers()
        self._forecasts = self._loader.load_demand_forecasts()
        # StockMonitor already loads its own data; positions are always fresh
        self._loaded_at = datetime.now()

    def reload(self):
        self._reload()
        self._monitor.reload()

    # ------------------------------------------------------------------
    # Core formula (pure, no I/O — testable in isolation)
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_reorder_point(
        average_daily_demand: float,
        lead_time_days: int,
        safety_stock: float = 0.0,
    ) -> float:
        """
        Reorder Point = average_daily_demand × lead_time_days + safety_stock

        Args:
            average_daily_demand: expected_qty / horizon (from demand forecast)
            lead_time_days:       supplier lead time in days
            safety_stock:         safety-stock buffer (0 until I3 is implemented)

        Returns:
            reorder_point as a float (may be fractional; round only for display)
        """
        return average_daily_demand * lead_time_days + safety_stock

    @staticmethod
    def calculate_inventory_position(
        available_stock: float,
        in_transit: float,
    ) -> float:
        """
        inventory_position = available_stock + in_transit

        Represents the stock available to the business once all in-transit
        units arrive. I2 uses this — not available_stock alone — to compare
        against the reorder point, which avoids triggering duplicate reorders
        for units already on order.
        """
        return available_stock + in_transit

    @staticmethod
    def calculate_suggested_qty(
        reorder_point: float,
        inventory_position: float,
    ) -> float:
        """
        suggested_reorder_qty = max(0, reorder_point - inventory_position)

        Never returns a negative quantity — the product may already be
        above the reorder point if in_transit was large.
        """
        return max(0.0, reorder_point - inventory_position)

    # ------------------------------------------------------------------
    # Supplier lookup (category-based placeholder)
    # ------------------------------------------------------------------

    def _resolve_supplier(self, category: str) -> Optional[Supplier]:
        """
        Match a product category to a supplier via the CATEGORY_SUPPLIER_MAP.

        The supplier 'category' field in suppliers.csv uses slash-separated
        strings (e.g. "Bakery/Dairy"). This method does a case-insensitive
        substring search.

        Assumption: supplier data is category-level, not product-level.
        Full product-supplier mapping is a Procurement domain responsibility.

        Fallback: if no category match is found, returns the supplier with
        the highest lead_time_days (most conservative / safest assumption).
        """
        category_lower = category.lower().strip()
        keyword = CATEGORY_SUPPLIER_MAP.get(category_lower)

        if keyword:
            for supplier in self._suppliers.values():
                if keyword in supplier.category.lower():
                    return supplier

        # Fallback: conservative — use the supplier with the longest lead time
        if self._suppliers:
            return max(self._suppliers.values(), key=lambda s: s.lead_time_days)
        return None

    # ------------------------------------------------------------------
    # Reason builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reason(
        product_name: str,
        store_id: str,
        inventory_position: float,
        reorder_point: float,
        average_daily_demand: float,
        lead_time_days: int,
        safety_stock: float,
        reorder_needed: bool,
        suggested_qty: float,
    ) -> str:
        """Build a concise, human-readable explanation of the I2 decision."""
        rop_str = f"{reorder_point:.2f}"
        pos_str = f"{inventory_position:.2f}"
        dmd_str = f"{average_daily_demand:.4f}"

        if reorder_needed:
            reason = (
                f"Reorder recommended: inventory position ({pos_str} units) "
                f"is at or below the reorder point ({rop_str} units). "
                f"Forecast demand is {dmd_str} units/day and supplier lead "
                f"time is {lead_time_days} day(s)"
            )
            if safety_stock > 0:
                reason += f" with a safety-stock buffer of {safety_stock:.2f} units"
            reason += f". Suggested order quantity: {suggested_qty:.0f} units."
        else:
            reason = (
                f"No reorder needed: inventory position ({pos_str} units) "
                f"exceeds the reorder point ({rop_str} units). "
                f"Forecast demand is {dmd_str} units/day and supplier lead "
                f"time is {lead_time_days} day(s)."
            )
        return reason

    # ------------------------------------------------------------------
    # Evaluate one product
    # ------------------------------------------------------------------

    def evaluate_product(
        self,
        position: InventoryPosition,
        safety_stock: float = 0.0,
    ) -> Optional[ReorderNeed]:
        """
        Evaluate whether a single product needs reordering.

        Args:
            position:     InventoryPosition from I1 (do not recalculate stock here)
            safety_stock: safety-stock buffer — 0 until I3 is implemented

        Returns:
            ReorderNeed if both forecast and supplier data are available,
            None if insufficient data (safe-failure: never invent values).
        """
        forecast = self._forecasts.get(position.product_id)
        if forecast is None:
            return None   # insufficient data — no forecast available

        supplier = self._resolve_supplier(position.category)
        if supplier is None:
            return None   # insufficient data — no supplier available

        # --- Core calculation ---
        avg_daily_demand = forecast.expected_qty / forecast.horizon
        inv_position = self.calculate_inventory_position(
            position.available_stock, position.in_transit
        )
        rop = self.calculate_reorder_point(avg_daily_demand, supplier.lead_time_days, safety_stock)
        reorder_needed = inv_position <= rop
        suggested_qty = self.calculate_suggested_qty(rop, inv_position) if reorder_needed else 0.0

        reason = self._build_reason(
            product_name=position.product_name,
            store_id=position.store_id,
            inventory_position=inv_position,
            reorder_point=rop,
            average_daily_demand=avg_daily_demand,
            lead_time_days=supplier.lead_time_days,
            safety_stock=safety_stock,
            reorder_needed=reorder_needed,
            suggested_qty=suggested_qty,
        )

        return ReorderNeed(
            product_id=position.product_id,
            sku=position.sku,
            product_name=position.product_name,
            category=position.category,
            store_id=position.store_id,
            available_stock=position.available_stock,
            in_transit=position.in_transit,
            inventory_position=inv_position,
            average_daily_demand=avg_daily_demand,
            demand_forecast=forecast.expected_qty,
            forecast_horizon=forecast.horizon,
            forecast_confidence=forecast.confidence,
            supplier_id=supplier.supplier_id,
            supplier_name=supplier.name,
            lead_time_days=supplier.lead_time_days,
            safety_stock=safety_stock,
            safety_stock_source=SAFETY_STOCK_SOURCE_PLACEHOLDER,
            reorder_point=rop,
            reorder_needed=reorder_needed,
            suggested_reorder_qty=suggested_qty,
            reason=reason,
            generated_at=datetime.now(),
        )

    # ------------------------------------------------------------------
    # Build AgentResult wrapper
    # ------------------------------------------------------------------

    def _build_agent_result(
        self,
        need: ReorderNeed,
    ) -> AgentResult:
        """Wrap a ReorderNeed in an AgentResult recommendation."""
        now = datetime.now()
        # Re-evaluate after one supplier lead time cycle
        expires_at = now + timedelta(days=need.lead_time_days)

        if need.reorder_needed:
            action_type = "REORDER"
            action = "PLACE_REORDER"
            # Confidence is moderated by forecast confidence and safety-stock completeness
            # (safety_stock=0 is a conservative fallback → slight confidence reduction)
            confidence = need.forecast_confidence * 0.9
            risk_level = "LOW" if need.inventory_position > 0 else "MEDIUM"
        else:
            action_type = "NO_ACTION"
            action = "HOLD"
            confidence = need.forecast_confidence
            risk_level = "LOW"

        evidence_refs = [
            f"inventory_snapshots.csv/{need.product_id}",
            f"demand_forecasts.json/{need.product_id}",
            f"suppliers.csv/{need.supplier_id}",
        ]

        return AgentResult(
            recommendation_id=f"I2-{uuid.uuid4().hex[:8].upper()}",
            agent_id=AGENT_ID,
            entity_type="product",
            entity_id=need.product_id,
            action_type=action_type,
            action=action,
            rationale=need.reason,
            evidence_refs=evidence_refs,
            confidence=confidence,
            risk_level=risk_level,
            requires_approval=True,       # always — I2 never auto-executes
            model_or_rule_version=RULE_VERSION,
            generated_at=now,
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # Public API — evaluate all products
    # ------------------------------------------------------------------

    def evaluate_all(
        self,
        store_id: Optional[str] = None,
        safety_stock: float = 0.0,
    ) -> List[Tuple[ReorderNeed, AgentResult]]:
        """
        Evaluate all active products and return (ReorderNeed, AgentResult) pairs.

        Products with missing forecast or supplier data are silently skipped
        (safe-failure: insufficient_data products returned separately via
        get_insufficient_data_products()).

        Args:
            store_id:     filter by store (None = all stores)
            safety_stock: global safety-stock buffer (0 until I3 is live)

        Returns:
            List of (ReorderNeed, AgentResult) tuples, sorted by urgency:
            reorder_needed=True first, then by inventory_position ascending.
        """
        positions = self._monitor.get_inventory_positions(store_id=store_id)
        results: List[Tuple[ReorderNeed, AgentResult]] = []

        for pos in positions:
            need = self.evaluate_product(pos, safety_stock=safety_stock)
            if need is None:
                continue
            ar = self._build_agent_result(need)
            results.append((need, ar))

        # Sort: reorder_needed first, then by inventory_position ascending
        results.sort(
            key=lambda t: (
                0 if t[0].reorder_needed else 1,
                t[0].inventory_position,
            )
        )
        return results

    def get_reorder_decisions(
        self,
        store_id: Optional[str] = None,
        safety_stock: float = 0.0,
    ) -> List[dict]:
        """
        Return all I2 reorder decisions as serialisable dicts.

        Each dict combines the ReorderNeed evidence with the AgentResult
        recommendation so a single API call returns a complete picture.
        """
        results = self.evaluate_all(store_id=store_id, safety_stock=safety_stock)
        output = []
        for need, ar in results:
            d = need.to_dict()
            d["recommendation"] = ar.to_dict()
            output.append(d)
        return output

    def get_urgent_reorders(
        self,
        store_id: Optional[str] = None,
        safety_stock: float = 0.0,
    ) -> List[dict]:
        """
        Return only products where reorder_needed = True, sorted by
        inventory_position ascending (most urgent first).
        """
        return [
            d for d in self.get_reorder_decisions(store_id=store_id, safety_stock=safety_stock)
            if d["reorder_needed"]
        ]

    def get_decision_for_product(
        self,
        product_id: str,
        store_id: Optional[str] = None,
        safety_stock: float = 0.0,
    ) -> Optional[dict]:
        """
        Return the I2 decision for a single product, or None if not found
        or insufficient data.
        """
        positions = self._monitor.get_inventory_positions(store_id=store_id)
        pos = next((p for p in positions if p.product_id == product_id), None)
        if pos is None:
            return None

        need = self.evaluate_product(pos, safety_stock=safety_stock)
        if need is None:
            return None   # insufficient data

        ar = self._build_agent_result(need)
        d = need.to_dict()
        d["recommendation"] = ar.to_dict()
        return d

    def get_insufficient_data_products(
        self,
        store_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Return products for which I2 cannot produce a decision due to
        missing forecast or supplier data.

        Safe-failure: these products are flagged rather than having values
        invented for them.
        """
        positions = self._monitor.get_inventory_positions(store_id=store_id)
        missing = []
        for pos in positions:
            forecast = self._forecasts.get(pos.product_id)
            supplier = self._resolve_supplier(pos.category)
            reasons = []
            if forecast is None:
                reasons.append("no_demand_forecast")
            if supplier is None:
                reasons.append("no_supplier_lead_time")
            if reasons:
                missing.append({
                    "product_id": pos.product_id,
                    "product_name": pos.product_name,
                    "category": pos.category,
                    "insufficient_data_reasons": reasons,
                })
        return missing
