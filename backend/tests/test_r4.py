from datetime import datetime, timedelta, timezone

import pytest

from app.coordination.coordinator import ProcurementCoordinator
from app.data.output_repository import OutputRepository


@pytest.mark.asyncio
async def test_r4_generates_governed_purchase_recommendation(repo):
    result = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert result.agent_id == "R4"
    assert result.action_type == "PurchaseRecommendation"
    assert result.status.value == "READY_FOR_REVIEW"
    assert result.requires_approval is True
    assert result.action["qty"] >= 260
    assert result.action["supplier_id"] in {"SUP-001", "SUP-002", "SUP-003"}
    assert result.action["decision_score"] > 0


@pytest.mark.asyncio
async def test_r4_respects_no_reorder(repo):
    result = await ProcurementCoordinator(repo).recommend_purchase("SKU-200", "tester")
    assert result.action_type == "NoPurchaseRequired"
    assert result.status.value == "APPROVED"


@pytest.mark.asyncio
async def test_r4_fails_safe_on_stale_external_contract(repo):
    """A stale I2 ReorderNeed in shared state must not be consumed silently."""
    outputs = OutputRepository(repo)
    current = outputs.get_latest_output("ReorderNeed", "SKU-100")
    assert current is not None, "fixture must have seeded a fresh I2 contract"

    stale_at = datetime.now(timezone.utc) - timedelta(days=5)
    stale_payload = {**current.payload, "generated_at": stale_at.isoformat()}
    # Publish a newer-by-write but older-by-generated_at record directly to
    # state, simulating an upstream agent that republished stale evidence.
    repo.upsert("agent_state", {
        **current.model_dump(mode="json"),
        "output_id": f"I2-SKU-100-stale",
        "payload": stale_payload,
        "generated_at": stale_at.isoformat(),
    }, "state_id")

    result = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert result.status.value == "DRAFT"
    assert "stale_dependency" in result.guardrails
    assert "I2" in " ".join(result.rationale)
