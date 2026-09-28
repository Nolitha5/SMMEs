"""Shared 25-agent exchange-layer contracts.

These are the cross-domain shapes every agent in the shared system publishes
and consumes. Procurement-specific payload models stay in `models.py`; this
module defines only the envelope and the exchange/governance records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.models import RiskLevel, utcnow

SCHEMA_VERSION = "1.0"
PROCUREMENT_DOMAIN = "procurement"

PROCUREMENT_AGENTS = frozenset({"R1", "R2", "R3", "R4", "R5"})

# Evidence contracts: analytical outputs that inform decisions. They live in
# agent_outputs/agent_state only and never carry approval semantics, whatever
# their risk tier. Elevated risk raises a system_event, not a review item.
EVIDENCE_OUTPUT_TYPES = frozenset({
    "SupplierComparison",        # R1
    "SupplierReliabilityScore",  # R2
    "LeadTimeRisk",              # R3
    "NoPurchaseRequired",        # R4 decision record when nothing is needed
    "ProcurementException",      # R5 reconciliation facts
})

# Action contracts: a human is being asked to approve, modify or reject
# something. These — and only these — are routed to agent_recommendations.
ACTION_OUTPUT_TYPES = frozenset({
    "PurchaseRecommendation",    # R4: create a purchase order
    "ReconciliationReview",      # R5-derived: accept exceptions and close a PO
})

PROCUREMENT_OUTPUT_TYPES = EVIDENCE_OUTPUT_TYPES | ACTION_OUTPUT_TYPES

# Upstream contracts Procurement consumes. Keyed by the publishing agent.
UPSTREAM_CONTRACTS = {
    "D4": ("demand", "DemandForecast"),
    "I1": ("inventory", "InventoryPosition"),
    "I2": ("inventory", "ReorderNeed"),
    "I3": ("inventory", "SafetyStockTarget"),
}

# Output types no Procurement code may ever publish.
FOREIGN_OUTPUT_TYPES = frozenset(
    {name for _, name in UPSTREAM_CONTRACTS.values()} | {"PriceRecommendation", "CustomerSegment"}
)

# Exchange + governance collections. Written only by the trusted backend.
COLLECTION_AGENT_OUTPUTS = "agent_outputs"
COLLECTION_AGENT_STATE = "agent_state"
COLLECTION_AGENT_RUNS = "agent_runs"
COLLECTION_SYSTEM_EVENTS = "system_events"
COLLECTION_AGENT_RECOMMENDATIONS = "agent_recommendations"
COLLECTION_APPROVAL_LOG = "approval_log"
COLLECTION_OUTCOMES = "outcomes"

PROTECTED_COLLECTIONS = frozenset({
    COLLECTION_AGENT_OUTPUTS,
    COLLECTION_AGENT_STATE,
    COLLECTION_AGENT_RUNS,
    COLLECTION_SYSTEM_EVENTS,
    COLLECTION_APPROVAL_LOG,
    COLLECTION_OUTCOMES,
})

# Operational collections. Procurement is the canonical writer for the first
# group and a reader only for the second.
PROCUREMENT_OPERATIONAL_COLLECTIONS = frozenset({
    "suppliers", "supplier_quotes", "supplier_performance",
    "purchase_orders", "goods_receipts", "invoices",
})
SHARED_READ_ONLY_COLLECTIONS = frozenset({"products", "inventory_snapshots", "inventory_movements"})


def state_id(agent_id: str, output_type: str, entity_id: str) -> str:
    """Deterministic `agent_state` document id: one latest projection per key."""
    return f"{agent_id}:{output_type}:{entity_id}"


class SharedAgentOutput(BaseModel):
    """Common envelope for every published agent contract."""

    output_id: str
    agent_id: str
    domain: str
    output_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    input_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    generated_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    model_or_rule_version: str
    run_id: str
    schema_version: str = SCHEMA_VERSION
    state_id: str | None = None

    def with_state_id(self) -> "SharedAgentOutput":
        self.state_id = state_id(self.agent_id, self.output_type, self.entity_id)
        return self


class AgentRun(BaseModel):
    """Execution trace for one agent invocation."""

    run_id: str
    agent_id: str
    domain: str
    entity_type: str
    entity_id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"] = "RUNNING"
    duration_ms: int | None = None
    model_or_rule_version: str
    schema_version: str = SCHEMA_VERSION
    input_refs: list[str] = Field(default_factory=list)
    output_id: str | None = None
    actor_id: str = "system"
    error: str | None = None


class SystemEvent(BaseModel):
    """Routing / trigger record on the shared event layer."""

    event_id: str
    event_type: str
    producer_domain: str
    producer_agent: str | None = None
    entity_type: str
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = "system"
    created_at: datetime = Field(default_factory=utcnow)
    processed: bool = False
    schema_version: str = SCHEMA_VERSION


class Outcome(BaseModel):
    """Actual procurement result, used for evaluation and R2/R3 feedback.

    References the `supplier_performance` row rather than duplicating it.
    """

    outcome_id: str
    domain: str = PROCUREMENT_DOMAIN
    recommendation_id: str | None
    purchase_order_id: str
    supplier_id: str
    product_id: str
    performance_id: str
    promised_date: str
    actual_date: str
    ordered_qty: float
    received_qty: float
    fill_rate: float
    defect_rate: float
    price_variance: float
    delivery_variance_days: int
    reconciliation_status: str
    exception_count: int
    reconciliation_output_id: str | None = None
    recorded_at: datetime = Field(default_factory=utcnow)
    schema_version: str = SCHEMA_VERSION


class InventoryPosition(BaseModel):
    """I1 published contract. Interface only — Inventory owns the implementation."""

    product_id: str
    on_hand: float = Field(ge=0)
    on_order: float = Field(default=0, ge=0)
    allocated: float = Field(default=0, ge=0)
    available: float
    generated_at: datetime = Field(default_factory=utcnow)
    source_version: str = "external"
