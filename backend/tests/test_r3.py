import pytest

from app.agents.procurement.r3_lead_time_risk import LeadTimeRiskAgent
from app.contracts.models import AgentContext


@pytest.mark.asyncio
async def test_r3_uses_robust_historical_metrics(repo):
    result = await LeadTimeRiskAgent(repo).run(AgentContext(entity_type="supplier", entity_id="SUP-003"))
    assert result.action["sample_size"] == 4
    assert result.action["p90_days"] >= result.action["median_days"]
    assert result.action["delay_rate"] > 0


@pytest.mark.asyncio
async def test_r3_falls_back_to_quote(repo):
    repo.upsert("suppliers", {"supplier_id": "SUP-X", "name": "New", "status": "ACTIVE", "payment_terms_days": 30, "currency": "ZAR"}, "supplier_id")
    repo.upsert("supplier_quotes", {"quote_id": "Q-X", "supplier_id": "SUP-X", "product_id": "SKU-X", "unit_cost": 2, "moq": 1, "quoted_lead_time_days": 6, "currency": "ZAR", "valid_from": "2026-09-01T00:00:00Z", "valid_until": "2026-10-01T00:00:00Z", "observed_at": "2026-09-08T00:00:00Z"}, "quote_id")
    result = await LeadTimeRiskAgent(repo).run(AgentContext(entity_type="supplier", entity_id="SUP-X"))
    assert result.action["expected_days"] == 6
    assert "quoted_lead_time_fallback" in result.guardrails
