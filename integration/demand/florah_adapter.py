"""Canonical integration boundary for Florah Demand D1-D5.

Florah owns forecasting logic. This module only maps her stable DemandForecast
contract into the shared 25-agent wire contract. No demand algorithm lives here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_VERSION = "florah-demand-e3534ef"


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def canonicalize_d4(native: Any) -> dict[str, Any]:
    """Convert Florah's DemandForecast/Pydantic object or dict to canonical D4."""
    if hasattr(native, "model_dump"):
        raw = native.model_dump(mode="json")
    elif isinstance(native, dict):
        raw = dict(native)
    else:
        raise TypeError("Florah D4 result must be a Pydantic model or dict")

    product_id = raw.get("product_id")
    horizon = raw.get("horizon_days", raw.get("horizon"))
    required = {
        "product_id": product_id,
        "horizon_days": horizon,
        "expected_qty": raw.get("expected_qty"),
        "lower_bound": raw.get("lower_bound"),
        "upper_bound": raw.get("upper_bound"),
        "confidence": raw.get("confidence"),
        "generated_at": raw.get("generated_at"),
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError("Florah D4 missing canonical fields: " + ", ".join(missing))

    expected = float(raw["expected_qty"])
    lower = float(raw["lower_bound"])
    upper = float(raw["upper_bound"])
    confidence = float(raw["confidence"])
    if int(horizon) <= 0:
        raise ValueError("horizon_days must be positive")
    if min(expected, lower, upper) < 0:
        raise ValueError("forecast quantities cannot be negative")
    if not lower <= expected <= upper:
        raise ValueError("forecast bounds must satisfy lower <= expected <= upper")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")

    return {
        "product_id": str(product_id),
        "horizon_days": int(horizon),
        "expected_qty": expected,
        "lower_bound": lower,
        "upper_bound": upper,
        "confidence": confidence,
        "drivers": list(raw.get("drivers") or []),
        "generated_at": _iso(raw["generated_at"]),
        "source_version": SOURCE_VERSION,
    }


def shared_output_from_d4(native: Any, *, business_id: str, run_id: str) -> dict[str, Any]:
    payload = canonicalize_d4(native)
    entity_id = payload["product_id"]
    generated = payload["generated_at"]
    return {
        "outputId": f"D4-DemandForecast-{entity_id}-{run_id}",
        "businessId": business_id,
        "capabilityId": "D4",
        "sourceAgent": "demand",
        "domain": "demand",
        "outputType": "DemandForecast",
        "entityType": "product",
        "entityId": entity_id,
        "payload": payload,
        "inputRefs": ["D1:CleanDemandSeries", "D2:SeasonalityProfile", "D3:DemandSignalAdjustment"],
        "confidence": payload["confidence"],
        "riskLevel": "LOW" if payload["confidence"] >= 0.70 else "MEDIUM",
        "generatedAt": generated,
        "expiresAt": None,
        "modelOrRuleVersion": SOURCE_VERSION,
        "runId": run_id,
        "correlationId": run_id,
        "idempotencyKey": f"D4:{entity_id}:{generated}",
    }
