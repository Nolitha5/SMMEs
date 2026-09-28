from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.models import AgentResult, ApprovalStatus, RiskLevel
from app.contracts.shared import EVIDENCE_OUTPUT_TYPES
from app.core.config import get_settings


HIGH_IMPACT_ACTIONS = {"PurchaseRecommendation", "ReconciliationReview"}


def finalize_agent_result(result: AgentResult) -> AgentResult:
    """Apply cross-cutting governance: approval, expiry, fail-safe status."""
    settings = get_settings()
    guardrails = list(result.guardrails)

    if "insufficient_evidence" in guardrails:
        result.status = ApprovalStatus.DRAFT
        result.requires_approval = True
        return result

    # Evidence contracts (R1–R3, R5 facts, R4's no-purchase record) inform a
    # decision; they are not one. An elevated risk tier never turns evidence
    # into a review item — that would ask a manager to "approve" a measurement.
    if result.action_type in EVIDENCE_OUTPUT_TYPES:
        result.requires_approval = False
        result.status = ApprovalStatus.APPROVED
    else:
        if result.action_type in HIGH_IMPACT_ACTIONS or result.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
            result.requires_approval = True
        result.status = ApprovalStatus.READY_FOR_REVIEW if result.requires_approval else ApprovalStatus.APPROVED

    if result.expires_at and result.expires_at <= datetime.now(timezone.utc):
        result.status = ApprovalStatus.EXPIRED
    return result


def second_review_required(expected_cost: float, risk_level: RiskLevel) -> bool:
    settings = get_settings()
    return expected_cost >= settings.max_po_value_without_second_review or risk_level == RiskLevel.HIGH


def can_execute(result: dict) -> tuple[bool, str | None]:
    status = result.get("status")
    if status not in {ApprovalStatus.APPROVED.value, ApprovalStatus.MODIFIED.value}:
        return False, "Recommendation must be APPROVED or MODIFIED before execution."
    if result.get("agent_id") != "R4":
        return False, "Only R4 purchase recommendations can create purchase orders."
    return True, None
