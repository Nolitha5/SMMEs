"""Regression tests for malformed supplier/quote records reaching R1.

Root cause being guarded: R1 indexed `supplier["supplier_id"]` and
`supplier["name"]` directly, and coerced quote numerics with bare `float(...)`.
The repository enforces no schema, so a single incomplete document raised
KeyError/ValueError and failed the whole comparison with HTTP 500.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.procurement.r1_supplier_comparator import SupplierComparatorAgent
from app.contracts.models import AgentContext
from app.coordination.coordinator import ProcurementCoordinator
from app.main import app


def _ctx(product_id: str = "SKU-100", qty: float = 260):
    return AgentContext(entity_type="product", entity_id=product_id, payload={"requested_qty": qty})


async def _run_r1(repo, product_id: str = "SKU-100", qty: float = 260):
    return await SupplierComparatorAgent(repo).run(_ctx(product_id, qty))


def _ranked_ids(result) -> list[str]:
    return [r["supplier_id"] for r in result.action["ranked_suppliers"]]


def _guardrail_count(result, prefix: str) -> int:
    for g in result.guardrails:
        if g.startswith(prefix):
            return int(g.split(":", 1)[1])
    return 0


# ---------------------------------------------------------------------------
# 1. Valid records are unaffected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_suppliers_still_rank_normally(repo):
    result = await _run_r1(repo)
    ranked = result.action["ranked_suppliers"]
    assert len(ranked) == 3
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    # Ranks must be ordered by descending score.
    assert [r["score"] for r in ranked] == sorted((r["score"] for r in ranked), reverse=True)
    assert not any(g.startswith("malformed_") for g in result.guardrails)


@pytest.mark.asyncio
async def test_screening_does_not_change_ranking_of_valid_data(repo):
    """Deterministic behaviour: screening must not alter scores or order."""
    first = await _run_r1(repo)
    second = await _run_r1(repo)
    assert _ranked_ids(first) == _ranked_ids(second)
    assert [r["score"] for r in first.action["ranked_suppliers"]] == [
        r["score"] for r in second.action["ranked_suppliers"]
    ]


# ---------------------------------------------------------------------------
# 2–5. Individual malformed shapes alongside valid suppliers
# ---------------------------------------------------------------------------


MALFORMED_SUPPLIERS = {
    "missing_supplier_id": {"name": "No Id Co", "status": "ACTIVE", "payment_terms_days": 30},
    "empty_supplier_id": {"supplier_id": "   ", "name": "Blank Id Co", "status": "ACTIVE"},
    "missing_name": {"supplier_id": "SUP-BAD-1", "status": "ACTIVE", "payment_terms_days": 30},
    "empty_name": {"supplier_id": "SUP-BAD-2", "name": "", "status": "ACTIVE"},
    "invalid_status": {"supplier_id": "SUP-BAD-3", "name": "Bad Status Co", "status": "NOT_A_STATUS"},
    "negative_payment_terms": {"supplier_id": "SUP-BAD-4", "name": "Neg Terms Co", "status": "ACTIVE", "payment_terms_days": -5},
    "non_numeric_payment_terms": {"supplier_id": "SUP-BAD-5", "name": "Bad Terms Co", "status": "ACTIVE", "payment_terms_days": "thirty"},
}


@pytest.mark.parametrize("label", sorted(MALFORMED_SUPPLIERS))
@pytest.mark.asyncio
async def test_malformed_supplier_does_not_break_comparison(repo, label):
    repo.append("suppliers", dict(MALFORMED_SUPPLIERS[label]))

    result = await _run_r1(repo)

    # The three seeded suppliers still rank.
    assert len(result.action["ranked_suppliers"]) == 3
    assert set(_ranked_ids(result)) == {"SUP-001", "SUP-002", "SUP-003"}
    # And the bad record is reported, not silently dropped.
    assert _guardrail_count(result, "malformed_suppliers_excluded") >= 1
    assert any("failed schema validation" in line for line in result.rationale)


@pytest.mark.asyncio
async def test_r1_never_raises_key_error_on_malformed_supplier(repo):
    """The original failure mode was a bare KeyError. Assert it cannot recur."""
    repo.append("suppliers", {"name": "No Id Co", "status": "ACTIVE"})
    repo.append("suppliers", {"supplier_id": "SUP-BAD-9", "status": "ACTIVE"})  # no name

    try:
        result = await _run_r1(repo)
    except KeyError as exc:  # pragma: no cover - regression guard
        pytest.fail(f"R1 raised KeyError on malformed supplier data: {exc}")

    assert result.action["ranked_suppliers"], "valid suppliers must still be ranked"


@pytest.mark.asyncio
async def test_malformed_quote_records_are_excluded(repo):
    """Malformed quote numerics previously crashed float() coercion."""
    repo.append("supplier_quotes", {
        "quote_id": "Q-BAD-1", "supplier_id": "SUP-001", "product_id": "SKU-100",
        "unit_cost": "not-a-number", "moq": 10,
    })
    repo.append("supplier_quotes", {
        "quote_id": "Q-BAD-2", "supplier_id": "SUP-002", "product_id": "SKU-100",
        "unit_cost": -5, "moq": 10,
    })
    repo.append("supplier_quotes", {  # missing unit_cost entirely
        "quote_id": "Q-BAD-3", "supplier_id": "SUP-003", "product_id": "SKU-100", "moq": 10,
    })

    result = await _run_r1(repo)

    assert len(result.action["ranked_suppliers"]) == 3, "valid quotes must still rank"
    assert _guardrail_count(result, "malformed_quotes_excluded") == 3


@pytest.mark.asyncio
async def test_malformed_coverage_data_is_excluded(repo):
    """available_qty is the product-coverage input; garbage must not crash scoring."""
    repo.append("supplier_quotes", {
        "quote_id": "Q-BAD-COV", "supplier_id": "SUP-001", "product_id": "SKU-100",
        "unit_cost": 18.0, "moq": 10, "available_qty": "plenty",
    })

    result = await _run_r1(repo)

    assert _guardrail_count(result, "malformed_quotes_excluded") == 1
    assert len(result.action["ranked_suppliers"]) == 3


@pytest.mark.asyncio
async def test_blank_optional_field_is_tolerated_not_excluded(repo):
    """An empty optional value means "unknown" and must stay usable."""
    repo.append("supplier_quotes", {
        "quote_id": "Q-BLANK", "supplier_id": "SUP-001", "product_id": "SKU-300",
        "unit_cost": 12.0, "moq": 5, "available_qty": "", "payment_terms_days": "",
    })

    result = await _run_r1(repo, product_id="SKU-300", qty=10)

    assert _guardrail_count(result, "malformed_quotes_excluded") == 0
    assert _ranked_ids(result) == ["SUP-001"]


@pytest.mark.asyncio
async def test_non_object_record_is_excluded(repo):
    """A stray non-object row must be screened out rather than crash iteration."""
    repo.append("suppliers", "this is not a record")

    result = await _run_r1(repo)

    assert len(result.action["ranked_suppliers"]) == 3
    assert _guardrail_count(result, "malformed_suppliers_excluded") == 1


# ---------------------------------------------------------------------------
# 6 + 10. Everything malformed → safe, non-actionable result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_suppliers_malformed_fails_safe(repo):
    for supplier_id in ("SUP-001", "SUP-002", "SUP-003"):
        repo.delete("suppliers", supplier_id, "supplier_id")
    repo.append("suppliers", {"name": "No Id A", "status": "ACTIVE"})
    repo.append("suppliers", {"supplier_id": "", "name": "Blank B", "status": "ACTIVE"})
    repo.append("suppliers", {"supplier_id": "SUP-C", "status": "ACTIVE"})

    result = await _run_r1(repo)

    assert result.status.value == "DRAFT", "must not be actionable"
    assert result.action["ranked_suppliers"] == [], "must not fabricate a supplier selection"
    assert result.confidence == 0.0
    assert "insufficient_evidence" in result.guardrails
    assert _guardrail_count(result, "malformed_suppliers_excluded") == 3
    assert any("failed schema validation" in line for line in result.rationale)


@pytest.mark.asyncio
async def test_all_quotes_malformed_fails_safe(repo):
    for quote in repo.list("supplier_quotes"):
        if quote.get("product_id") == "SKU-100":
            repo.delete("supplier_quotes", quote["quote_id"], "quote_id")
    repo.append("supplier_quotes", {"quote_id": "Q-A", "supplier_id": "SUP-001", "product_id": "SKU-100", "unit_cost": 0})
    repo.append("supplier_quotes", {"quote_id": "Q-B", "supplier_id": "SUP-002", "product_id": "SKU-100", "unit_cost": "abc"})

    result = await _run_r1(repo)

    assert result.status.value == "DRAFT"
    assert result.action["ranked_suppliers"] == []
    assert "insufficient_evidence" in result.guardrails
    assert _guardrail_count(result, "malformed_quotes_excluded") == 2


# ---------------------------------------------------------------------------
# 9. R4 still works when malformed records coexist with valid ones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_still_recommends_with_malformed_suppliers_present(repo):
    """Run the real R1→R2/R3→R4 chain, not R4 in isolation.

    R4 fail-safes without its full I2/I3/D4/R2/R3 evidence, so only the
    coordinator exercises the path this regression cares about.
    """
    baseline = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")
    assert baseline.action_type == "PurchaseRecommendation"
    assert baseline.action["supplier_id"], "baseline must produce a real selection"

    repo.append("suppliers", {"name": "No Id Co", "status": "ACTIVE"})
    repo.append("supplier_quotes", {
        "quote_id": "Q-BAD-R4", "supplier_id": "SUP-001", "product_id": "SKU-100", "unit_cost": "oops",
    })

    result = await ProcurementCoordinator(repo).recommend_purchase("SKU-100", "tester")

    assert result.action_type == "PurchaseRecommendation"
    assert result.status.value == "READY_FOR_REVIEW", "malformed neighbours must not block a valid recommendation"
    assert result.action["supplier_id"] in {"SUP-001", "SUP-002", "SUP-003"}
    # The malformed records changed nothing about the decision itself.
    assert result.action["supplier_id"] == baseline.action["supplier_id"]
    assert result.action["qty"] == baseline.action["qty"]


# ---------------------------------------------------------------------------
# 8. HTTP surface must not 500 because of one malformed record
# ---------------------------------------------------------------------------


def test_api_does_not_return_500_for_malformed_supplier():
    with TestClient(app) as client:
        from app.data.factory import get_repository

        repo = get_repository()
        repo.append("suppliers", {"name": "Broken Co", "status": "ACTIVE"})
        try:
            response = client.post("/api/v1/procurement/recommend/SKU-100")
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["agent_id"] == "R4"
        finally:
            repo.delete("suppliers", "Broken Co", "name")


def test_api_comparison_endpoint_reports_exclusions():
    with TestClient(app) as client:
        from app.data.factory import get_repository

        repo = get_repository()
        repo.append("suppliers", {"supplier_id": "SUP-NONAME", "status": "ACTIVE"})
        try:
            response = client.post("/api/v1/agents/R1/run", json={
                "entity_type": "product", "entity_id": "SKU-100", "payload": {"requested_qty": 260},
            })
            assert response.status_code == 200, response.text
            body = response.json()
            assert any(g.startswith("malformed_suppliers_excluded") for g in body["guardrails"])
        finally:
            repo.delete("suppliers", "SUP-NONAME", "supplier_id")
