"""Shared `system_events` publishing.

Events are routing and trigger records on the shared layer: something happened
that another agent, domain or the coordinator may need to react to. They are
NOT an audit log — the audit history is composed on read from the canonical
collections by `services/audit_history.py`. Operational bookkeeping such as
"a CSV was imported" is not an event; it is not a trigger for anyone.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.contracts.shared import COLLECTION_SYSTEM_EVENTS, PROCUREMENT_DOMAIN, SystemEvent
from app.data.repository import Repository

# Triggers Procurement raises for the shared system. Names marked [BP] are
# specified verbatim in the 25-Agent Blueprint's coordination table (p13) or the
# Firebase architecture (p8); consumers in other domains match on them exactly.
EVENT_PURCHASE_RECOMMENDATION_CREATED = "purchase.recommendation.created"  # [BP] → approval queue
EVENT_RECOMMENDATION_APPROVED = "recommendation.approved"       # [BP] → UI / action executor
EVENT_RECOMMENDATION_MODIFIED = "recommendation.modified"
EVENT_RECOMMENDATION_REJECTED = "recommendation.rejected"
EVENT_PURCHASE_ORDER_CREATED = "purchase_order.created"         # → Inventory in-transit
EVENT_PURCHASE_ORDER_CLOSED = "purchase_order.closed"
EVENT_GOODS_RECEIPT_RECORDED = "goods.receipt.recorded"         # → reconciliation eligibility
EVENT_INVOICE_RECEIVED = "invoice.received"                     # → reconciliation eligibility
EVENT_RECONCILIATION_COMPLETED = "procurement.reconciliation.completed"
EVENT_EXCEPTION_CREATED = "procurement.exception.created"
EVENT_SUPPLIER_PERFORMANCE_UPDATED = "supplier.performance.updated"  # [BP] → R2/R3 re-evaluation, R4, Inventory
EVENT_OUTCOME_RECORDED = "outcome.recorded"                     # [BP] → D5 + domain evaluators
EVENT_EVIDENCE_RISK_ELEVATED = "procurement.evidence.risk_elevated"  # R1–R3 MEDIUM/HIGH signal, not a review item

# The Blueprint names the approval trigger per decision, not one generic event,
# so a consumer can subscribe to approvals without filtering payloads.
DECISION_EVENTS = {
    "APPROVED": EVENT_RECOMMENDATION_APPROVED,
    "MODIFIED": EVENT_RECOMMENDATION_MODIFIED,
    "REJECTED": EVENT_RECOMMENDATION_REJECTED,
}


def deterministic_event_id(event_type: str, entity_id: str, idempotency_key: str) -> str:
    digest = sha256(f"{event_type}|{entity_id}|{idempotency_key}".encode()).hexdigest()
    return f"EVT-{digest[:16]}"


def publish_event(
    repo: Repository,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor_id: str,
    payload: dict[str, Any] | None = None,
    *,
    producer_agent: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Publish one event.

    With an `idempotency_key` the event id is deterministic and a retried
    publish is a no-op. Without one the id is random and each call is a new
    event — appropriate for genuinely distinct occurrences.
    """
    event_id = (
        deterministic_event_id(event_type, entity_id, idempotency_key)
        if idempotency_key
        else f"EVT-{uuid4().hex[:16]}"
    )
    event = SystemEvent(
        event_id=event_id,
        event_type=event_type,
        producer_domain=PROCUREMENT_DOMAIN,
        producer_agent=producer_agent,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        actor_id=actor_id,
    )
    data = event.model_dump(mode="json")
    repo.insert_if_absent(COLLECTION_SYSTEM_EVENTS, data, "event_id")
    return data
