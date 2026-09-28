import pytest

from app.coordination.coordinator import ProcurementCoordinator


@pytest.mark.asyncio
async def test_r5_match_for_clean_po(repo):
    result = await ProcurementCoordinator(repo).reconcile("PO-DEMO-001", "tester")
    assert result.action["match_status"] == "MATCH"
    assert result.action["exception_types"] == []
    assert result.status.value == "APPROVED"


@pytest.mark.asyncio
async def test_r5_detects_three_way_mismatches(repo):
    result = await ProcurementCoordinator(repo).reconcile("PO-DEMO-002", "tester")
    types = set(result.action["exception_types"])
    assert "UNDER_DELIVERY" in types
    assert "PRICE_VARIANCE" in types
    assert "DEFECTIVE_GOODS" in types
    assert "LATE_DELIVERY" in types
    # The R5 output is evidence and is published as such; the review a manager
    # must give is a separate ReconciliationReview action derived from it.
    assert result.status.value == "APPROVED"
    assert result.action_recommendation_id
    review = repo.get("agent_recommendations", result.action_recommendation_id, "recommendation_id")
    assert review["action_type"] == "ReconciliationReview"
    assert review["status"] == "READY_FOR_REVIEW"
    assert review["source_output_id"] == result.output_id


@pytest.mark.asyncio
async def test_r5_fails_safe_without_evidence(repo):
    result = await ProcurementCoordinator(repo).reconcile("PO-NOT-THERE", "tester")
    assert result.action["match_status"] == "INSUFFICIENT_EVIDENCE"
    assert result.status.value == "DRAFT"
