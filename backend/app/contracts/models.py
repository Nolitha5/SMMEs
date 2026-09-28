from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ApprovalStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class AgentContext(BaseModel):
    store_id: str = "STORE-001"
    entity_type: str
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prior_outputs: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = "system"
    # Concrete ids/versions of the evidence the coordinator resolved for this
    # run. Merged into the published output's input_refs for traceability.
    input_refs: list[str] = Field(default_factory=list)
    run_id: str | None = None


class AgentResult(BaseModel):
    """Working result an agent returns.

    `recommendation_id` doubles as the shared `output_id`. The shared-envelope
    fields (`output_id`, `domain`, `input_refs`, `run_id`, `schema_version`)
    are populated by the coordinator/output repository; `SharedAgentOutput` is
    derived from this object for publication.
    """

    recommendation_id: str
    agent_id: Literal["R1", "R2", "R3", "R4", "R5"]
    entity_type: str
    entity_id: str
    action_type: str
    action: dict[str, Any]
    rationale: list[str]
    evidence_refs: list[str]
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    requires_approval: bool
    model_or_rule_version: str
    generated_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.DRAFT
    guardrails: list[str] = Field(default_factory=list)
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    # Shared-architecture envelope fields.
    output_id: str | None = None
    domain: str = "procurement"
    input_refs: list[str] = Field(default_factory=list)
    run_id: str | None = None
    schema_version: str = "1.0"
    # For an action record: the evidence output it was derived from.
    source_output_id: str | None = None
    # For an evidence output: the separate human action it gave rise to, if any
    # (e.g. an R5 MISMATCH spawns a ReconciliationReview).
    action_recommendation_id: str | None = None


class AgentStatus(BaseModel):
    agent_id: str
    name: str
    version: str
    enabled: bool = True
    last_run_at: datetime | None = None
    last_error: str | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["APPROVED", "MODIFIED", "REJECTED"]
    modified_action: dict[str, Any] | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def modification_requires_action(self):
        if self.decision == "MODIFIED" and not self.modified_action:
            raise ValueError("modified_action is required when decision=MODIFIED")
        return self


class Supplier(BaseModel):
    supplier_id: str
    name: str
    status: Literal["ACTIVE", "SUSPENDED", "INACTIVE"] = "ACTIVE"
    payment_terms_days: int = Field(default=30, ge=0)
    currency: str = "ZAR"
    contact_email: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class SupplierQuote(BaseModel):
    quote_id: str
    supplier_id: str
    product_id: str
    unit_cost: float = Field(gt=0)
    moq: float = Field(default=1, gt=0)
    quoted_lead_time_days: float = Field(default=7, gt=0)
    available_qty: float | None = Field(default=None, ge=0)
    payment_terms_days: int | None = Field(default=None, ge=0)
    currency: str = "ZAR"
    valid_from: datetime = Field(default_factory=utcnow)
    valid_until: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)


class SupplierPerformance(BaseModel):
    performance_id: str
    supplier_id: str
    po_id: str
    order_date: date
    promised_date: date
    actual_date: date
    ordered_qty: float = Field(gt=0)
    received_qty: float = Field(ge=0)
    defect_qty: float = Field(default=0, ge=0)
    invoice_variance_pct: float = 0.0

    @property
    def fill_rate(self) -> float:
        return min(self.received_qty / self.ordered_qty, 1.0) if self.ordered_qty else 0.0

    @property
    def defect_rate(self) -> float:
        return min(self.defect_qty / self.received_qty, 1.0) if self.received_qty else 0.0


# External published contracts from the Demand and Inventory teams. These are interfaces only.
class ReorderNeed(BaseModel):
    product_id: str
    reorder_point: float = Field(ge=0)
    projected_position: float
    reorder_needed: bool
    recommended_qty: float = Field(ge=0)
    generated_at: datetime = Field(default_factory=utcnow)
    source_version: str = "external"


class SafetyStockTarget(BaseModel):
    product_id: str
    safety_stock: float = Field(ge=0)
    service_level: float = Field(ge=0, le=1)
    lead_time_days: float = Field(gt=0)
    generated_at: datetime = Field(default_factory=utcnow)
    source_version: str = "external"


class DemandForecast(BaseModel):
    product_id: str
    horizon_days: int = Field(gt=0)
    expected_qty: float = Field(ge=0)
    lower_bound: float = Field(ge=0)
    upper_bound: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    drivers: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)
    source_version: str = "external"

    @field_validator("drivers", mode="before")
    @classmethod
    def parse_drivers(cls, value):
        if isinstance(value, str):
            return [x.strip() for x in value.split("|") if x.strip()]
        return value

    @model_validator(mode="after")
    def bounds_are_ordered(self):
        if self.lower_bound > self.expected_qty or self.expected_qty > self.upper_bound:
            raise ValueError("forecast bounds must satisfy lower <= expected <= upper")
        return self


class SupplierRank(BaseModel):
    supplier_id: str
    supplier_name: str
    score: float = Field(ge=0, le=1)
    rank: int = Field(ge=1)
    unit_cost: float
    moq: float
    quoted_lead_time_days: float
    payment_terms_days: int
    score_breakdown: dict[str, float]
    warnings: list[str] = Field(default_factory=list)


class SupplierComparison(BaseModel):
    product_id: str
    requested_qty: float
    ranked_suppliers: list[SupplierRank]
    generated_at: datetime = Field(default_factory=utcnow)


class SupplierReliabilityScore(BaseModel):
    supplier_id: str
    score: float = Field(ge=0, le=1)
    on_time_rate: float = Field(ge=0, le=1)
    fill_rate: float = Field(ge=0, le=1)
    defect_rate: float = Field(ge=0, le=1)
    invoice_accuracy: float = Field(ge=0, le=1)
    sample_size: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class LeadTimeRisk(BaseModel):
    supplier_id: str
    median_days: float = Field(gt=0)
    expected_days: float = Field(gt=0)
    p90_days: float = Field(gt=0)
    variability_days: float = Field(ge=0)
    delay_rate: float = Field(ge=0, le=1)
    risk: RiskLevel
    sample_size: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class PurchaseRecommendation(BaseModel):
    supplier_id: str
    product_id: str
    qty: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    expected_cost: float = Field(gt=0)
    eta_days: float = Field(gt=0)
    supplier_score: float = Field(ge=0, le=1)
    reliability_score: float = Field(ge=0, le=1)
    lead_time_risk: RiskLevel
    risk: RiskLevel
    currency: str = "ZAR"
    decision_score: float = Field(ge=0, le=1)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class PurchaseOrder(BaseModel):
    po_id: str
    recommendation_id: str
    supplier_id: str
    product_id: str
    qty: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    currency: str = "ZAR"
    ordered_at: datetime = Field(default_factory=utcnow)
    promised_date: date
    status: Literal["OPEN", "PARTIALLY_RECEIVED", "RECEIVED", "CLOSED", "CANCELLED"] = "OPEN"
    created_by: str

    @property
    def total(self) -> float:
        return round(self.qty * self.unit_cost, 2)


class GoodsReceipt(BaseModel):
    receipt_id: str
    po_id: str
    supplier_id: str
    product_id: str
    qty_received: float = Field(ge=0)
    qty_defective: float = Field(default=0, ge=0)
    received_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def defects_not_above_received(self):
        if self.qty_defective > self.qty_received:
            raise ValueError("qty_defective cannot exceed qty_received")
        return self


class SupplierInvoice(BaseModel):
    invoice_id: str
    invoice_number: str
    po_id: str
    supplier_id: str
    product_id: str
    qty_invoiced: float = Field(gt=0)
    unit_cost: float = Field(gt=0)
    tax_amount: float = Field(default=0, ge=0)
    currency: str = "ZAR"
    invoiced_at: datetime = Field(default_factory=utcnow)

    @property
    def subtotal(self) -> float:
        return round(self.qty_invoiced * self.unit_cost, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax_amount, 2)


class ProcurementException(BaseModel):
    supplier_id: str
    po_id: str
    exception_types: list[str]
    details: dict[str, Any]
    match_status: Literal["MATCH", "PARTIAL_MATCH", "MISMATCH", "INSUFFICIENT_EVIDENCE"]
    financial_variance: float = 0.0
    severity: RiskLevel


class ImportResult(BaseModel):
    collection: str
    imported: int
    rejected: int
    duplicate_ids: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class AuditEvent(BaseModel):
    audit_id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
