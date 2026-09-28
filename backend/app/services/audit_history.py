"""Audit history composed from the canonical shared collections.

There is no standalone audit collection. The decision trail is reconstructed
on read from the records the shared architecture already keeps:

    agent_runs              → an agent ran (or failed)
    agent_outputs           → a contract was published
    agent_recommendations   → a human action was raised
    approval_log            → a human decided
    system_events           → a routing/trigger signal fired
    outcomes                → an actual result was recorded

`system_events` is deliberately *not* the audit log: it carries triggers only.
"""

from __future__ import annotations

from typing import Any

from app.contracts.shared import (
    COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_AGENT_RUNS,
    COLLECTION_APPROVAL_LOG, COLLECTION_OUTCOMES, COLLECTION_SYSTEM_EVENTS,
)
from app.data.repository import Repository


def _entry(source: str, event_id: str, created_at: Any, event_type: str, entity_type: str,
           entity_id: Any, actor_id: Any, payload: dict | None = None) -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "created_at": str(created_at or ""),
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": str(entity_id or ""),
        "actor_id": str(actor_id or "system"),
        "payload": payload or {},
    }


def build_audit_history(repo: Repository, *, entity_id: str | None = None, limit: int = 500) -> list[dict]:
    """Merge the canonical collections into one newest-first timeline."""
    rows: list[dict] = []

    for run in repo.list(COLLECTION_AGENT_RUNS):
        status = run.get("status")
        rows.append(_entry(
            COLLECTION_AGENT_RUNS, f"run:{run.get('run_id')}",
            run.get("completed_at") or run.get("started_at"),
            f"agent.run.{str(status or 'unknown').lower()}",
            run.get("entity_type", ""), run.get("entity_id"), run.get("actor_id"),
            {"agent_id": run.get("agent_id"), "run_id": run.get("run_id"), "output_id": run.get("output_id"),
             "duration_ms": run.get("duration_ms"), "error": run.get("error")},
        ))

    for out in repo.list(COLLECTION_AGENT_OUTPUTS):
        rows.append(_entry(
            COLLECTION_AGENT_OUTPUTS, f"output:{out.get('output_id')}", out.get("generated_at"),
            f"output.published.{out.get('output_type')}",
            out.get("entity_type", ""), out.get("entity_id"), "system",
            {"agent_id": out.get("agent_id"), "output_id": out.get("output_id"), "run_id": out.get("run_id"),
             "risk_level": out.get("risk_level"), "confidence": out.get("confidence")},
        ))

    for rec in repo.list(COLLECTION_AGENT_RECOMMENDATIONS):
        rows.append(_entry(
            COLLECTION_AGENT_RECOMMENDATIONS, f"recommendation:{rec.get('recommendation_id')}", rec.get("generated_at"),
            f"recommendation.raised.{rec.get('action_type')}",
            "recommendation", rec.get("recommendation_id"), "system",
            {"agent_id": rec.get("agent_id"), "entity_id": rec.get("entity_id"), "status": rec.get("status"),
             "source_output_id": rec.get("source_output_id"), "risk_level": rec.get("risk_level")},
        ))

    for log in repo.list(COLLECTION_APPROVAL_LOG):
        rows.append(_entry(
            COLLECTION_APPROVAL_LOG, f"approval:{log.get('approval_id')}", log.get("decided_at"),
            f"recommendation.{str(log.get('decision', '')).lower()}",
            "recommendation", log.get("recommendation_id"), log.get("reviewer"),
            {"reason": log.get("reason"), "modified_action": log.get("modified_action")},
        ))

    for ev in repo.list(COLLECTION_SYSTEM_EVENTS):
        rows.append(_entry(
            COLLECTION_SYSTEM_EVENTS, ev.get("event_id", ""), ev.get("created_at"),
            ev.get("event_type", ""), ev.get("entity_type", ""), ev.get("entity_id"), ev.get("actor_id"),
            ev.get("payload") or {},
        ))

    for out in repo.list(COLLECTION_OUTCOMES):
        rows.append(_entry(
            COLLECTION_OUTCOMES, f"outcome:{out.get('outcome_id')}", out.get("recorded_at"),
            "outcome.recorded", "purchase_order", out.get("purchase_order_id"), "system",
            {"recommendation_id": out.get("recommendation_id"), "reconciliation_status": out.get("reconciliation_status"),
             "exception_count": out.get("exception_count"), "fill_rate": out.get("fill_rate")},
        ))

    if entity_id:
        rows = [r for r in rows if r["entity_id"] == entity_id or r["payload"].get("entity_id") == entity_id
                or r["payload"].get("recommendation_id") == entity_id or r["payload"].get("output_id") == entity_id]

    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]
