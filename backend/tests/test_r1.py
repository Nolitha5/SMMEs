import pytest

from app.agents.procurement.r1_supplier_comparator import SupplierComparatorAgent
from app.contracts.models import AgentContext


@pytest.mark.asyncio
async def test_r1_ranks_all_eligible_suppliers(repo):
    result = await SupplierComparatorAgent(repo).run(AgentContext(entity_type="product", entity_id="SKU-100", payload={"requested_qty": 260}))
    assert result.action_type == "SupplierComparison"
    assert len(result.action["ranked_suppliers"]) == 3
    assert result.action["ranked_suppliers"][0]["rank"] == 1
    assert 0 <= result.action["ranked_suppliers"][0]["score"] <= 1


@pytest.mark.asyncio
async def test_r1_fails_safely_without_quotes(repo):
    result = await SupplierComparatorAgent(repo).run(AgentContext(entity_type="product", entity_id="UNKNOWN", payload={"requested_qty": 10}))
    assert result.status.value == "DRAFT"
    assert "insufficient_evidence" in result.guardrails
