from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.contracts.models import AgentContext, AgentResult, RiskLevel, utcnow
from app.core.config import get_settings
from app.data.repository import Repository
from app.governance.policies import finalize_agent_result


class BaseProcurementAgent:
    agent_id = "R0"
    name = "Base"
    version = "1.0.0"

    def __init__(self, repo: Repository):
        self.repo = repo

    def rows(self, collection: str, **filters) -> list[dict]:
        rows = self.repo.list(collection)
        for key, value in filters.items():
            rows = [r for r in rows if str(r.get(key)) == str(value)]
        return rows

    def result(
        self,
        context: AgentContext,
        action_type: str,
        action: dict,
        rationale: list[str],
        evidence_refs: list[str],
        confidence: float,
        risk: RiskLevel = RiskLevel.LOW,
        requires_approval: bool = False,
        guardrails: list[str] | None = None,
        expires_hours: int | None = None,
    ) -> AgentResult:
        ttl = expires_hours if expires_hours is not None else get_settings().recommendation_ttl_hours
        output_id = f"REC-{uuid4().hex[:16]}"
        # Concrete upstream ids resolved by the coordinator come first; the
        # agent's own evidence labels follow. Order is preserved, duplicates dropped.
        merged_refs = list(dict.fromkeys([*context.input_refs, *evidence_refs]))
        result = AgentResult(
            recommendation_id=output_id,
            output_id=output_id,
            input_refs=merged_refs,
            run_id=context.run_id,
            agent_id=self.agent_id,
            entity_type=context.entity_type,
            entity_id=context.entity_id,
            action_type=action_type,
            action=action,
            rationale=rationale,
            evidence_refs=evidence_refs,
            confidence=max(0.0, min(float(confidence), 1.0)),
            risk_level=risk,
            requires_approval=requires_approval,
            model_or_rule_version=self.version,
            generated_at=utcnow(),
            expires_at=utcnow() + timedelta(hours=ttl),
            guardrails=guardrails or [],
            input_snapshot={
                "store_id": context.store_id,
                "entity_type": context.entity_type,
                "entity_id": context.entity_id,
                "payload": context.payload,
                "prior_output_ids": sorted(context.prior_outputs.keys()),
            },
        )
        return finalize_agent_result(result)
