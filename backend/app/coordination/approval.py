from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.contracts.models import ApprovalDecision, ApprovalStatus
from app.contracts.shared import COLLECTION_AGENT_RECOMMENDATIONS, COLLECTION_APPROVAL_LOG, SCHEMA_VERSION
from app.data.repository import Repository
from app.services import events


class ApprovalService:
    """The only writer of `approval_log`. Neither agents nor the frontend write it."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def decide(self, recommendation_id: str, decision: ApprovalDecision, reviewer: str) -> dict:
        rec = self.repo.get(COLLECTION_AGENT_RECOMMENDATIONS, recommendation_id, "recommendation_id")
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        if rec.get("status") in {ApprovalStatus.EXECUTED.value, ApprovalStatus.REJECTED.value, ApprovalStatus.EXPIRED.value}:
            raise HTTPException(status_code=409, detail=f"Recommendation is already {rec.get('status')}")
        if rec.get("status") == ApprovalStatus.DRAFT.value:
            raise HTTPException(status_code=409, detail="DRAFT recommendation is not eligible for approval")

        new_status = ApprovalStatus(decision.decision)
        if decision.decision == "MODIFIED":
            original = dict(rec.get("action") or {})
            modified = dict(original)
            modified.update(decision.modified_action or {})
            rec["action"] = modified
        decided_at = datetime.now(timezone.utc).isoformat()
        rec["status"] = new_status.value
        rec["reviewed_by"] = reviewer
        rec["reviewed_at"] = decided_at
        rec["review_reason"] = decision.reason

        log = {
            "approval_id": f"APR-{uuid4().hex[:16]}",
            "recommendation_id": recommendation_id,
            "reviewer": reviewer,
            "decision": decision.decision,
            "modified_action": decision.modified_action,
            "reason": decision.reason,
            "decided_at": decided_at,
            "schema_version": SCHEMA_VERSION,
        }
        # Status change and its journal entry commit together.
        self.repo.write_batch([
            ("upsert", COLLECTION_AGENT_RECOMMENDATIONS, rec, "recommendation_id"),
            ("insert_if_absent", COLLECTION_APPROVAL_LOG, log, "approval_id"),
        ])
        events.publish_event(
            self.repo, events.DECISION_EVENTS[decision.decision], "recommendation", recommendation_id, reviewer, log,
            producer_agent=rec.get("agent_id"), idempotency_key=log["approval_id"],
        )
        return rec
