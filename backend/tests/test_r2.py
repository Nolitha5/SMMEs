import pytest

from app.agents.procurement.r2_supplier_reliability import SupplierReliabilityAgent
from app.contracts.models import AgentContext


@pytest.mark.asyncio
async def test_r2_distinguishes_good_and_poor_supplier(repo):
    agent = SupplierReliabilityAgent(repo)
    good = await agent.run(AgentContext(entity_type="supplier", entity_id="SUP-002"))
    poor = await agent.run(AgentContext(entity_type="supplier", entity_id="SUP-003"))
    assert good.action["score"] > poor.action["score"]
    assert good.action["on_time_rate"] > poor.action["on_time_rate"]


@pytest.mark.asyncio
async def test_r2_uses_neutral_prior_for_new_supplier(repo):
    result = await SupplierReliabilityAgent(repo).run(AgentContext(entity_type="supplier", entity_id="SUP-NEW"))
    assert result.action["score"] == 0.5
    assert result.action["sample_size"] == 0
    assert "limited_history" in result.guardrails
