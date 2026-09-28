"""
AgentResult — shared recommendation output contract for all Inventory agents.

Each agent (I1–I5) produces typed AgentResult objects to communicate its
decision to an orchestrator, a UI, or a human approver.

This is a RECOMMENDATION ONLY.
No agent may execute purchases or modify inventory directly.
Every AgentResult with requires_approval=True must be approved by a human
before any downstream action is taken.

Fields:
    recommendation_id  : unique ID for this recommendation (I2-<hex>)
    agent_id           : identifies the producing agent (e.g. "I2_REORDER_POINT")
    entity_type        : the domain object this decision concerns ("product")
    entity_id          : product_id (or store/sku, etc.)
    action_type        : class of action (e.g. "REORDER", "ALERT", "REVIEW")
    action             : specific action label (e.g. "PLACE_REORDER")
    rationale          : human-readable explanation of the decision
    evidence_refs      : list of data sources or IDs used as evidence
    confidence         : 0.0–1.0 confidence in this recommendation
    risk_level         : "LOW" | "MEDIUM" | "HIGH"
    requires_approval  : always True for I2 reorder recommendations
    model_or_rule_version : version tag of the rule set that produced this
    generated_at       : ISO timestamp
    expires_at         : ISO timestamp after which recommendation should be re-evaluated
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class AgentResult:
    """
    Shared output contract for Inventory domain agents.
    I2 uses this to package its reorder recommendation alongside the
    ReorderNeed evidence object.
    """

    recommendation_id: str
    agent_id: str                    # e.g. "I2_REORDER_POINT"
    entity_type: str                 # "product"
    entity_id: str                   # product_id
    action_type: str                 # "REORDER" | "NO_ACTION" | "ALERT"
    action: str                      # "PLACE_REORDER" | "HOLD" | etc.
    rationale: str                   # human-readable explanation
    evidence_refs: List[str]         # data sources used
    confidence: float                # 0.0–1.0
    risk_level: str                  # "LOW" | "MEDIUM" | "HIGH"
    requires_approval: bool          # must be True for reorder recommendations
    model_or_rule_version: str       # e.g. "I2-v1.0-basic-rop"
    generated_at: datetime
    expires_at: Optional[datetime]   # re-evaluate after this timestamp

    def to_dict(self) -> dict:
        return {
            "recommendation_id": self.recommendation_id,
            "agent_id": self.agent_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action_type": self.action_type,
            "action": self.action,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "model_or_rule_version": self.model_or_rule_version,
            "generated_at": self.generated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
