"""`agent_runs` execution trace.

One record per agent invocation, written at start (RUNNING) and finalized at
completion (SUCCEEDED / FAILED). Together with `agent_outputs.input_refs` this
is what makes an end-to-end reconstruction of a decision possible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.contracts.shared import COLLECTION_AGENT_RUNS, PROCUREMENT_DOMAIN, AgentRun
from app.data.repository import Repository


def start_run(
    repo: Repository,
    agent_id: str,
    entity_type: str,
    entity_id: str,
    model_or_rule_version: str,
    actor_id: str = "system",
    input_refs: list[str] | None = None,
) -> AgentRun:
    run = AgentRun(
        run_id=f"RUN-{uuid4().hex[:16]}",
        agent_id=agent_id,
        domain=PROCUREMENT_DOMAIN,
        entity_type=entity_type,
        entity_id=entity_id,
        started_at=datetime.now(timezone.utc),
        model_or_rule_version=model_or_rule_version,
        actor_id=actor_id,
        input_refs=list(input_refs or []),
    )
    repo.upsert(COLLECTION_AGENT_RUNS, run.model_dump(mode="json"), "run_id")
    return run


def finish_run(
    repo: Repository,
    run: AgentRun,
    *,
    output_id: str | None = None,
    input_refs: list[str] | None = None,
    error: str | None = None,
) -> AgentRun:
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
    run.status = "FAILED" if error else "SUCCEEDED"
    run.output_id = output_id
    if input_refs is not None:
        run.input_refs = list(input_refs)
    # Error summary only — never the full exception with its internals.
    run.error = error[:500] if error else None
    repo.upsert(COLLECTION_AGENT_RUNS, run.model_dump(mode="json"), "run_id")
    return run


def latest_run_per_agent(repo: Repository) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in repo.list(COLLECTION_AGENT_RUNS):
        agent_id = row.get("agent_id")
        if not agent_id:
            continue
        if agent_id not in latest or str(row.get("started_at", "")) > str(latest[agent_id].get("started_at", "")):
            latest[agent_id] = row
    return latest
