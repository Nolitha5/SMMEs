from __future__ import annotations

import asyncio

from app.contracts.models import AgentContext
from app.coordination.coordinator import ProcurementCoordinator
from app.data.factory import get_repository


async def run_daily_procurement() -> dict:
    repo = get_repository()
    coordinator = ProcurementCoordinator(repo)
    refreshed = []
    for supplier in repo.list("suppliers"):
        if supplier.get("status") != "ACTIVE":
            continue
        supplier_id = supplier["supplier_id"]
        ctx = AgentContext(entity_type="supplier", entity_id=supplier_id, payload={"supplier_id": supplier_id}, actor_id="system:daily-worker")
        r2 = await coordinator.run_agent("R2", ctx)
        r3_ctx = AgentContext(
            entity_type="supplier", entity_id=supplier_id, payload={"supplier_id": supplier_id},
            prior_outputs={"R2": r2.action}, actor_id="system:daily-worker", input_refs=[r2.output_id],
        )
        r3 = await coordinator.run_agent("R3", r3_ctx)
        refreshed.append({"supplier_id": supplier_id, "r2": r2.output_id, "r3": r3.output_id})
    # Each R2/R3 run already left an agent_runs trace and published its
    # output; the job's completion is bookkeeping, not a trigger.
    return {"suppliers_refreshed": len(refreshed), "results": refreshed}


if __name__ == "__main__":
    print(asyncio.run(run_daily_procurement()))
