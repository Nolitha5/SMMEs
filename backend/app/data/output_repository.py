"""Single publication path for agent outputs on the shared exchange layer.

Every R1–R5 result goes through `OutputRepository.publish()`. Agents never
write `agent_outputs`, `agent_state` or `agent_recommendations` themselves, so
there is exactly one place that knows the envelope, the idempotency rule and
the ownership boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.contracts.models import AgentResult, RiskLevel
from app.contracts.shared import (
    ACTION_OUTPUT_TYPES, COLLECTION_AGENT_OUTPUTS, COLLECTION_AGENT_RECOMMENDATIONS,
    COLLECTION_AGENT_STATE, FOREIGN_OUTPUT_TYPES, PROCUREMENT_AGENTS, PROCUREMENT_DOMAIN,
    SCHEMA_VERSION, UPSTREAM_CONTRACTS, SharedAgentOutput, state_id,
)
from app.core.config import get_settings
from app.data.repository import Repository
from app.services.data_quality import is_stale


class OwnershipViolation(RuntimeError):
    """Raised when Procurement code tries to publish a contract it does not own."""


class StaleOutput(RuntimeError):
    pass


class OutputRepository:
    def __init__(self, repo: Repository):
        self.repo = repo

    # ------------------------------------------------------------------
    # Publication (Procurement-owned outputs only)
    # ------------------------------------------------------------------

    @staticmethod
    def envelope(result: AgentResult) -> SharedAgentOutput:
        if not result.output_id:
            raise ValueError("AgentResult.output_id must be set before publication")
        if not result.run_id:
            raise ValueError("AgentResult.run_id must be set before publication")
        return SharedAgentOutput(
            output_id=result.output_id,
            agent_id=result.agent_id,
            domain=result.domain,
            output_type=result.action_type,
            entity_type=result.entity_type,
            entity_id=result.entity_id,
            payload=result.action,
            input_refs=list(result.input_refs or result.evidence_refs),
            confidence=result.confidence,
            risk_level=result.risk_level,
            generated_at=result.generated_at,
            expires_at=result.expires_at,
            model_or_rule_version=result.model_or_rule_version,
            run_id=result.run_id,
            schema_version=result.schema_version or SCHEMA_VERSION,
        ).with_state_id()

    def _assert_owned(self, envelope: SharedAgentOutput) -> None:
        if envelope.domain != PROCUREMENT_DOMAIN:
            raise OwnershipViolation(f"Procurement cannot publish for domain '{envelope.domain}'")
        if envelope.agent_id not in PROCUREMENT_AGENTS:
            raise OwnershipViolation(f"'{envelope.agent_id}' is not a Procurement agent")
        if envelope.output_type in FOREIGN_OUTPUT_TYPES:
            raise OwnershipViolation(f"'{envelope.output_type}' is owned by another domain")

    def publish(self, result: AgentResult) -> SharedAgentOutput:
        """Publish one result: immutable record + latest state (+ recommendation).

        Idempotent on `output_id`: republishing the same output changes nothing.
        The immutable record is append-only; the state projection is replaced;
        both land in a single batch so a reader never sees one without the other.
        """
        env = self.envelope(result)
        self._assert_owned(env)

        record = env.model_dump(mode="json")
        ops: list[tuple[str, str, dict[str, Any], str]] = [
            ("insert_if_absent", COLLECTION_AGENT_OUTPUTS, record, "output_id"),
        ]

        # Only replace the state projection if this output is at least as new
        # as what is already there, so a delayed retry can't regress state.
        current = self.repo.get(COLLECTION_AGENT_STATE, env.state_id, "state_id")
        if not current or str(current.get("generated_at", "")) <= record["generated_at"]:
            ops.append(("upsert", COLLECTION_AGENT_STATE, record, "state_id"))

        # Only action contracts become review items. Evidence — however risky —
        # never does; the coordinator raises a system_event for elevated risk.
        if env.output_type in ACTION_OUTPUT_TYPES:
            rec = result.model_dump(mode="json")
            rec["source_output_id"] = result.source_output_id or env.output_id
            ops.append(("insert_if_absent", COLLECTION_AGENT_RECOMMENDATIONS, rec, "recommendation_id"))

        self.repo.write_batch(ops)
        return env

    # ------------------------------------------------------------------
    # Upstream fixtures — DEV/TEST COMPATIBILITY ONLY (never called by an agent)
    # ------------------------------------------------------------------

    def seed_upstream_contract(
        self,
        agent_id: str,
        entity_id: str,
        payload: dict[str, Any],
        *,
        entity_type: str = "product",
        confidence: float = 1.0,
        risk_level: RiskLevel = RiskLevel.LOW,
        generated_at: datetime | None = None,
        source_version: str = "external",
        run_id: str | None = None,
    ) -> SharedAgentOutput:
        """Write an upstream agent's contract *as that agent would have*.

        DEV/TEST COMPATIBILITY ONLY. Exists so local fixtures and CSV imports
        can stand in for the Demand and Inventory agents while Procurement runs
        standalone. Procurement is never the producer of these contracts: in
        the shared system this path is disabled (`ALLOW_UPSTREAM_FIXTURES=false`)
        and only Demand/Inventory write them. It is deliberately a separate
        entry point from `publish()` so the ownership check there stays absolute.
        """
        if not get_settings().allow_upstream_fixtures:
            raise OwnershipViolation(
                "Upstream contract seeding is disabled: Procurement is not the producer of "
                f"'{agent_id}' contracts in shared mode (ALLOW_UPSTREAM_FIXTURES=false)"
            )
        if agent_id not in UPSTREAM_CONTRACTS:
            raise OwnershipViolation(f"'{agent_id}' is not a recognised upstream contract producer")
        domain, output_type = UPSTREAM_CONTRACTS[agent_id]
        gen = generated_at or datetime.now(timezone.utc)
        output_id = f"{agent_id}-{entity_id}-{gen.strftime('%Y%m%dT%H%M%S')}"
        env = SharedAgentOutput(
            output_id=output_id,
            agent_id=agent_id,
            domain=domain,
            output_type=output_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            input_refs=[f"{agent_id}:{source_version}"],
            confidence=confidence,
            risk_level=risk_level,
            generated_at=gen,
            expires_at=None,
            model_or_rule_version=source_version,
            run_id=run_id or f"run-{output_id}",
        ).with_state_id()
        record = env.model_dump(mode="json")
        self.repo.write_batch([
            ("insert_if_absent", COLLECTION_AGENT_OUTPUTS, record, "output_id"),
            ("upsert", COLLECTION_AGENT_STATE, record, "state_id"),
        ])
        return env

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def get_latest_output(
        self,
        output_type: str,
        entity_id: str,
        *,
        agent_id: str | None = None,
        max_age_hours: float | None = None,
        payload_model: Type[BaseModel] | None = None,
        schema_version: str = SCHEMA_VERSION,
    ) -> SharedAgentOutput | None:
        """Latest valid state for a contract, or None if absent, stale or invalid.

        Returning None (rather than raising) is deliberate: the caller decides
        how to fail safe, and R4 already knows how to say "insufficient evidence".
        """
        if agent_id is None:
            agent_id = next((a for a, (_, t) in UPSTREAM_CONTRACTS.items() if t == output_type), None)
            if agent_id is None:
                agent_id = {
                    "SupplierComparison": "R1", "SupplierReliabilityScore": "R2",
                    "LeadTimeRisk": "R3", "PurchaseRecommendation": "R4",
                    "NoPurchaseRequired": "R4", "ProcurementException": "R5",
                }.get(output_type)
        if agent_id is None:
            return None

        raw = self.repo.get(COLLECTION_AGENT_STATE, state_id(agent_id, output_type, entity_id), "state_id")
        if not raw:
            return None
        try:
            env = SharedAgentOutput.model_validate(raw)
        except ValidationError:
            return None
        if env.schema_version.split(".")[0] != schema_version.split(".")[0]:
            return None
        if env.expires_at and env.expires_at <= datetime.now(timezone.utc):
            return None
        if max_age_hours is not None and is_stale(env.generated_at, max_age_hours):
            return None
        if payload_model is not None:
            try:
                payload_model.model_validate(env.payload)
            except ValidationError:
                return None
        return env

    def history(self, output_type: str, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = [
            r for r in self.repo.list(COLLECTION_AGENT_OUTPUTS)
            if r.get("output_type") == output_type and r.get("entity_id") == entity_id
        ]
        rows.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
        return rows[:limit]
