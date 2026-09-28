from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Type

from pydantic import BaseModel, ValidationError


PRIMARY_KEYS = {
    # Operational (Procurement-owned)
    "suppliers": "supplier_id",
    "supplier_quotes": "quote_id",
    "supplier_performance": "performance_id",
    "purchase_orders": "po_id",
    "goods_receipts": "receipt_id",
    "invoices": "invoice_id",
    # Shared read-only context
    "products": "product_id",
    "inventory_snapshots": "snapshot_id",
    "inventory_movements": "movement_id",
    # Agent exchange layer
    "agent_outputs": "output_id",
    "agent_state": "state_id",
    "system_events": "event_id",
    # Governance + evaluation
    "agent_recommendations": "recommendation_id",
    "approval_log": "approval_id",
    "agent_runs": "run_id",
    "outcomes": "outcome_id",
}


def validate_rows(rows: list[dict[str, Any]], model: Type[BaseModel], primary_key: str) -> tuple[list[dict], list[dict], int]:
    valid: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    duplicates = 0
    for index, row in enumerate(rows, start=1):
        try:
            parsed = model.model_validate(row)
            data = parsed.model_dump(mode="json")
            key = str(data.get(primary_key, ""))
            if not key:
                raise ValueError(f"missing primary key {primary_key}")
            if key in seen:
                duplicates += 1
                errors.append({"row": index, "reason": "duplicate_in_batch", "key": key})
                continue
            seen.add(key)
            valid.append(data)
        except (ValidationError, ValueError) as exc:
            errors.append({"row": index, "reason": str(exc)})
    return valid, errors, duplicates


def _describe(exc: ValidationError, limit: int = 3) -> str:
    """Compact, human-readable reason.

    Deliberately reports only field location and message — never the offending
    input value, which may hold operational data that does not belong in an
    agent rationale or audit note.
    """
    parts = []
    for error in exc.errors()[:limit]:
        field = ".".join(str(p) for p in error.get("loc", ())) or "record"
        parts.append(f"{field}: {error.get('msg', 'invalid')}")
    remaining = len(exc.errors()) - limit
    if remaining > 0:
        parts.append(f"(+{remaining} more)")
    return "; ".join(parts)


def screen_records(
    rows: list[Any], model: Type[BaseModel], primary_key: str
) -> tuple[list[dict], list[dict]]:
    """Split stored records into usable ones and excluded ones with reasons.

    Agents read from a schema-less store, so a single malformed document must
    not be able to fail a whole evaluation. Validity is defined by the same
    contract model the CSV importer uses, so there is one definition of valid.

    Differs from `validate_rows` in two ways that matter to agents: the original
    record is returned for anything usable, so downstream scoring sees exactly
    the values it saw before this screening existed; and nothing raises.

    A blank string is treated as an absent value. That keeps optional fields
    tolerant (an empty `available_qty` still means "unknown") while causing a
    blank identity field such as `supplier_id` to fail validation, which is the
    intended outcome.
    """
    usable: list[dict] = []
    excluded: list[dict] = []
    for raw in rows:
        if not isinstance(raw, dict):
            excluded.append({"key": "<unreadable>", "reason": "record is not an object"})
            continue
        candidate = {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in raw.items()}
        try:
            model.model_validate(candidate)
        except ValidationError as exc:
            key = raw.get(primary_key)
            excluded.append({
                "key": str(key).strip() if key not in (None, "") else f"<no {primary_key}>",
                "reason": _describe(exc),
            })
            continue
        usable.append(raw)
    return usable, excluded


def is_stale(generated_at, max_age_hours: float) -> bool:
    if generated_at is None:
        return True
    dt = generated_at if isinstance(generated_at, datetime) else datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() > max_age_hours * 3600
