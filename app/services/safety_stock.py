"""
I3 Safety Stock Agent — deterministic safety-stock calculation.

Responsibility: determine the safety-stock target for each product using
demand-forecast uncertainty and supplier reliability.

Formula (I3-v1):
    Step 1: expected_daily_demand = expected_qty / horizon
    Step 2: horizon_std = (upper_bound - lower_bound) / 4
    Step 3: daily_std = horizon_std / sqrt(horizon)
    Step 4: lead_time_demand_std = daily_std * sqrt(lead_time_days)
    Step 5: z = mapped from service_level (0.90→1.28, 0.95→1.65, 0.99→2.33)
    Step 6: reliability_factor = 1 + (1 - clamp(reliability_score, 0, 1))
    Step 7: raw_safety_stock = z * lead_time_demand_std * reliability_factor
    Step 8: safety_stock = ceil(raw_safety_stock), min 0

Boundaries:
  - Never negative
  - Missing forecast or supplier → None (safe-failure, no invented values)
  - reliability_score clamped to [0, 1] before use

I3 does NOT:
  - Implement reorder logic (I2)
  - Produce demand forecasts (D4)
  - Handle expiry or slow stock (I4)
  - Raise inventory exceptions (I5)

Uses only Python stdlib: math, csv, json, pathlib.
"""
from __future__ import annotations

import csv
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.models.safety_stock_target import SafetyStockTarget
from app.models.agent_result import AgentResult

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
AGENT_ID = "I3_SAFETY_STOCK"
RULE_VERSION = "I3-v1"
ACTION_TYPE = "SET_SAFETY_STOCK"

SERVICE_LEVEL_Z: Dict[float, float] = {
    0.90: 1.28,
    0.95: 1.65,
    0.99: 2.33,
}
DEFAULT_SERVICE_LEVEL = 0.95

# Confidence pass-through map
CONFIDENCE_MAP = {
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
}

# Category → supplier keyword map (mirrors I2)
CATEGORY_SUPPLIER_MAP: Dict[str, str] = {
    "bakery": "bakery",
    "dairy": "bakery",
    "staples": "staples",
    "canned goods": "staples",
    "condiments": "staples",
    "spreads": "staples",
    "breakfast": "staples",
    "beverages": "beverages",
    "snacks": "beverages",
    "confectionery": "beverages",
    "household": "household",
    "frozen": "frozen",
}


# ------------------------------------------------------------------
# Confidence mapping helper
# ------------------------------------------------------------------

def _map_confidence(raw) -> str:
    """Map confidence to HIGH/MEDIUM/LOW.

    Accepts either a float in [0, 1] or a string "HIGH"/"MEDIUM"/"LOW".
    """
    if isinstance(raw, str):
        return CONFIDENCE_MAP.get(raw.upper(), "MEDIUM")
    # float
    v = float(raw)
    if v >= 0.85:
        return "HIGH"
    if v >= 0.70:
        return "MEDIUM"
    return "LOW"


# ------------------------------------------------------------------
# Pure calculation helpers (all static, no side-effects)
# ------------------------------------------------------------------

def calculate_expected_daily_demand(expected_qty: float, horizon: int) -> float:
    """Step 1: average daily demand over the forecast horizon."""
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    return expected_qty / horizon


def calculate_horizon_std(upper_bound: float, lower_bound: float) -> float:
    """Step 2: approximate horizon-level std from 95% CI bounds.

    Raises ValueError if upper_bound < lower_bound (invalid forecast interval).
    Zero uncertainty is valid when upper_bound == lower_bound.
    """
    if upper_bound < lower_bound:
        raise ValueError(
            f"upper_bound ({upper_bound}) must be >= lower_bound ({lower_bound})"
        )
    return (upper_bound - lower_bound) / 4.0


def calculate_daily_std(horizon_std: float, horizon: int) -> float:
    """Step 3: convert horizon std to daily std."""
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    return horizon_std / math.sqrt(horizon)


def calculate_lead_time_demand_std(daily_std: float, lead_time_days: int) -> float:
    """Step 4: std of demand over the lead-time window."""
    if lead_time_days < 0:
        raise ValueError("lead_time_days must be non-negative")
    return daily_std * math.sqrt(lead_time_days)


def get_z_score(service_level: float) -> float:
    """Step 5: map service level to z-score; defaults to 0.95 if unknown."""
    return SERVICE_LEVEL_Z.get(service_level, SERVICE_LEVEL_Z[DEFAULT_SERVICE_LEVEL])


def calculate_reliability_factor(reliability_score: float) -> float:
    """Step 6: reliability_factor = 1 + (1 - clamped_score).
    reliability_score clamped to [0, 1] before use.
    """
    clamped = max(0.0, min(1.0, reliability_score))
    return 1.0 + (1.0 - clamped)


def calculate_raw_safety_stock(
    z: float,
    lead_time_demand_std: float,
    reliability_factor: float,
) -> float:
    """Step 7: raw (unclamped) safety stock."""
    return z * lead_time_demand_std * reliability_factor


def calculate_safety_stock(raw: float) -> int:
    """Step 8: ceil and floor at 0."""
    return max(0, math.ceil(raw))


# ------------------------------------------------------------------
# SafetyStockAgent
# ------------------------------------------------------------------

class SafetyStockAgent:
    """
    I3 Safety Stock Agent.

    Reads demand_forecasts.json and suppliers.csv from data_dir.
    Produces SafetyStockTarget + AgentResult for each product.
    """

    def __init__(
        self,
        data_dir: Path,
        service_level: float = DEFAULT_SERVICE_LEVEL,
    ):
        self._data_dir = Path(data_dir)
        self._service_level = service_level
        self._z = get_z_score(service_level)
        self._forecasts: Dict[str, dict] = self._load_forecasts()
        self._suppliers: List[dict] = self._load_suppliers()
        self._loaded_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_forecasts(self) -> Dict[str, dict]:
        path = self._data_dir / "demand_forecasts.json"
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        forecasts = {}
        for entry in raw:
            pid = entry.get("product_id", "").strip().upper()
            if pid:
                forecasts[pid] = entry
        return forecasts

    def _load_suppliers(self) -> List[dict]:
        path = self._data_dir / "suppliers.csv"
        suppliers = []
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                suppliers.append(row)
        return suppliers

    # ------------------------------------------------------------------
    # Supplier resolution (mirrors I2 pattern)
    # ------------------------------------------------------------------

    def _resolve_supplier(self, category: str) -> Optional[dict]:
        """Match category to supplier using keyword map; fallback = max lead_time."""
        cat_lower = (category or "").lower()
        keyword = None
        for cat_key, sup_key in CATEGORY_SUPPLIER_MAP.items():
            if cat_key in cat_lower:
                keyword = sup_key
                break

        if keyword:
            for sup in self._suppliers:
                sup_cats = sup.get("categories", "").lower()
                if keyword in sup_cats:
                    return sup

        # fallback: highest lead_time supplier
        if self._suppliers:
            return max(
                self._suppliers,
                key=lambda s: int(s.get("lead_time_days", 0)),
            )
        return None

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    def evaluate_product(
        self,
        product_id: str,
        category: str,
        store_id: Optional[str] = None,
        lead_time_risk_adjustment: float = 0.0,
    ) -> Optional[Tuple[SafetyStockTarget, AgentResult]]:
        """
        Produce (SafetyStockTarget, AgentResult) for one product.

        Returns None if forecast or supplier data is missing (safe-failure).

        Future R3 integration
        ---------------------
        ``lead_time_risk_adjustment`` is the hook for the Procurement team's
        R3 LeadTimeRisk contract.  When R3 is available it can supply an
        additive adjustment to the raw safety stock (e.g. +0.5 z-equivalent
        units of extra buffer due to observed lead-time variance).  Pass 0.0
        (the default) to run purely on local supplier reliability, which is
        the current MVP behaviour.

        Example future call::

            r3_signal = r3_agent.get_lead_time_risk(product_id)
            i3_agent.evaluate_product(
                product_id, category,
                lead_time_risk_adjustment=r3_signal.buffer_units,
            )
        """
        """
        Produce (SafetyStockTarget, AgentResult) for one product.

        Returns None if forecast or supplier data is missing (safe-failure).
        """
        pid = product_id.strip().upper()

        # Demand forecast
        forecast = self._forecasts.get(pid)
        if forecast is None:
            return None

        expected_qty = float(forecast.get("expected_qty", 0))
        # field is "horizon" in demand_forecasts.json (horizon_days is alias)
        horizon = int(forecast.get("horizon_days", forecast.get("horizon", 0)))
        upper_bound = float(forecast.get("upper_bound", 0))
        lower_bound = float(forecast.get("lower_bound", 0))
        # confidence may be a float (0.82) or string ("HIGH")
        raw_conf = forecast.get("confidence", 0.5)
        forecast_confidence = _map_confidence(raw_conf)

        if horizon <= 0:
            return None

        # Supplier
        supplier = self._resolve_supplier(category)
        if supplier is None:
            return None

        lead_time_days = int(supplier.get("lead_time_days", 0))
        raw_rel = supplier.get("reliability_score")
        reliability_used_fallback = raw_rel is None
        reliability_score_raw = float(raw_rel) if raw_rel is not None else 1.0

        # ---- I3 formula steps ----
        # Step 1
        daily_demand = calculate_expected_daily_demand(expected_qty, horizon)
        # Step 2
        h_std = calculate_horizon_std(upper_bound, lower_bound)
        # Step 3
        d_std = calculate_daily_std(h_std, horizon)
        # Step 4
        lt_demand_std = calculate_lead_time_demand_std(d_std, lead_time_days)
        # Step 5 — z already set from service_level on __init__
        z = self._z
        # Step 6
        rel_factor = calculate_reliability_factor(reliability_score_raw)
        # Step 7
        raw_ss = calculate_raw_safety_stock(z, lt_demand_std, rel_factor)
        # R3 LeadTimeRisk adjustment (future hook — currently 0.0 in local MVP)
        raw_ss_adjusted = raw_ss + lead_time_risk_adjustment
        # Step 8
        ss = calculate_safety_stock(raw_ss_adjusted)

        confidence_label = CONFIDENCE_MAP.get(forecast_confidence, "MEDIUM")
        confidence_score = {"HIGH": 0.90, "MEDIUM": 0.75, "LOW": 0.50}.get(
            confidence_label, 0.75
        )

        # Human-readable rationale
        pct_service = int(self._service_level * 100)
        rel_pct = int(reliability_score_raw * 100)
        supplier_name = supplier.get("name", supplier.get("supplier_name", "supplier"))
        reliability_note = " [fallback: no reliability data, assumed 100%]" if reliability_used_fallback else ""
        r3_note = f", R3 lead-time risk adjustment={round(lead_time_risk_adjustment,2)} units" if lead_time_risk_adjustment != 0.0 else " (R3 lead-time risk: not yet available — using supplier reliability only)"
        reason = (
            f"Safety stock of {ss} units calculated from forecast uncertainty "
            f"(daily σ={round(d_std,3)}), {lead_time_days}-day supplier lead time "
            f"({supplier_name}), supplier reliability {rel_pct}%{reliability_note}, "
            f"and a {pct_service}% target service level (z={z}){r3_note}. "
            f"Raw={round(raw_ss_adjusted,3)}, formula I3-v1."
        )

        now = datetime.now(timezone.utc)

        target = SafetyStockTarget(
            product_id=pid,
            safety_stock=ss,
            expected_daily_demand=daily_demand,
            forecast_uncertainty=d_std,
            lead_time_days=lead_time_days,
            reliability_score=reliability_score_raw,
            reliability_factor=rel_factor,
            service_level=self._service_level,
            z_score=z,
            raw_safety_stock=raw_ss,
            confidence=confidence_label,
            reason=reason,
            formula_version=RULE_VERSION,
        )

        agent_result = AgentResult(
            recommendation_id=f"I3-{uuid.uuid4().hex[:8].upper()}",
            agent_id=AGENT_ID,
            entity_type="PRODUCT",
            entity_id=pid,
            action_type=ACTION_TYPE,
            action=f"Set safety stock to {ss} units for product {pid}.",
            rationale=reason,
            evidence_refs=[pid],
            confidence=confidence_score,
            risk_level="LOW",
            requires_approval=False,
            model_or_rule_version=RULE_VERSION,
            generated_at=now,
            expires_at=now + timedelta(hours=24),
        )

        return target, agent_result

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_all_targets(
        self,
        products: Optional[List[dict]] = None,
        store_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Returns serialised dicts for all products that have sufficient data.

        ``products`` should be a list of dicts with at minimum
        {"product_id": ..., "category": ...}.  If None, falls back to
        iterating the forecast keys with category derived from forecast data.
        """
        results = []
        items = products if products is not None else self._fallback_product_list()

        for item in items:
            pid = item.get("product_id", "").strip().upper()
            category = item.get("category", "")
            pair = self.evaluate_product(pid, category, store_id=store_id)
            if pair is None:
                continue
            target, agent_result = pair
            results.append({
                **target.to_dict(),
                "recommendation": agent_result.to_dict(),
            })

        return results

    def get_target_for_product(
        self,
        product_id: str,
        category: str,
        store_id: Optional[str] = None,
        lead_time_risk_adjustment: float = 0.0,
    ) -> Optional[dict]:
        pair = self.evaluate_product(
            product_id,
            category,
            store_id=store_id,
            lead_time_risk_adjustment=lead_time_risk_adjustment,
        )
        if pair is None:
            return None
        target, agent_result = pair
        return {
            **target.to_dict(),
            "recommendation": agent_result.to_dict(),
        }

    def _fallback_product_list(self) -> List[dict]:
        """When no product list is provided, derive minimal items from forecast keys."""
        return [
            {"product_id": pid, "category": data.get("category", "")}
            for pid, data in self._forecasts.items()
        ]
