# External Integration Contracts

Procurement consumes external outputs through stable schemas in
`backend/app/contracts/models.py` and `backend/app/contracts/shared.py`.

## How contracts travel — the shared envelope

In the shared 25-agent system, upstream agents do not call Procurement. They
publish into the shared exchange layer, and R4 reads the latest projection from
`agent_state`. Each published contract is wrapped in the common
`SharedAgentOutput` envelope; the JSON bodies below are the `payload`.

```json
{
  "output_id":  "I2-SKU-100-20260914T103408",
  "agent_id":   "I2",
  "domain":     "inventory",
  "output_type": "ReorderNeed",
  "entity_type": "product",
  "entity_id":  "SKU-100",
  "payload":    { "...ReorderNeed fields below..." },
  "input_refs": ["I2:inventory-1.0"],
  "confidence": 1.0,
  "risk_level": "LOW",
  "generated_at": "2026-09-14T10:34:08Z",
  "expires_at": null,
  "model_or_rule_version": "inventory-1.0",
  "run_id":     "run-...",
  "schema_version": "1.0",
  "state_id":   "I2:ReorderNeed:SKU-100"
}
```

The `agent_state` document id is `state_id = "{agent_id}:{output_type}:{entity_id}"`.
Procurement reads by that id and nothing else.

## I1 — InventoryPosition (available, not required by current R4 logic)

```json
{
  "product_id": "SKU-100",
  "on_hand": 95,
  "on_order": 0,
  "allocated": 10,
  "available": 85,
  "generated_at": "2026-09-08T10:00:00Z",
  "source_version": "inventory-1.0"
}
```

## I2 — ReorderNeed

Required fields:

```json
{
  "product_id": "SKU-100",
  "reorder_point": 180,
  "projected_position": 95,
  "reorder_needed": true,
  "recommended_qty": 260,
  "generated_at": "2026-09-08T10:00:00Z",
  "source_version": "inventory-1.0"
}
```

## I3 — SafetyStockTarget

```json
{
  "product_id": "SKU-100",
  "safety_stock": 120,
  "service_level": 0.95,
  "lead_time_days": 5,
  "generated_at": "2026-09-08T10:00:00Z",
  "source_version": "inventory-1.0"
}
```

## D4 — DemandForecast

```json
{
  "product_id": "SKU-100",
  "horizon_days": 7,
  "expected_qty": 310,
  "lower_bound": 270,
  "upper_bound": 355,
  "confidence": 0.86,
  "drivers": ["weekend uplift", "local event"],
  "generated_at": "2026-09-08T10:00:00Z",
  "source_version": "demand-1.0"
}
```

## Freshness rule

R4 currently rejects I2/I3/D4 evidence older than 72 hours. This threshold is deliberately visible and test-covered so integration teams can agree a different SLA without changing agent internals.

## Producer/consumer rule

Other teams publish `SharedAgentOutput` envelopes into `agent_outputs` and
`agent_state`. Procurement never imports another domain's agent classes, never
writes another domain's outputs, and `OutputRepository.publish()` raises
`OwnershipViolation` if asked to.

**DEV/TEST COMPATIBILITY ONLY.** The Procurement import endpoints
(`/imports/demand_forecasts`, `/imports/inventory_positions`,
`/imports/reorder_needs`, `/imports/safety_stock_targets`) and the sample-data
bootstrap publish CSV rows into the exchange layer on the owning agent's behalf
so Procurement can run standalone. They are gated by `ALLOW_UPSTREAM_FIXTURES`
and **must be disabled (`false`) in the shared system**, where D4 comes only
from Demand and I1/I2/I3 only from Inventory. With the flag off the endpoints
return 403 and bootstrap skips the upstream seed.

## What Procurement publishes for others

| `state_id` pattern | Contract | Consumers |
|---|---|---|
| `R1:SupplierComparison:{product_id}` | ranked supplier offers | R4 |
| `R2:SupplierReliabilityScore:{supplier_id}` | reliability score | R3, R4, Inventory |
| `R3:LeadTimeRisk:{supplier_id}` | expected / P90 lead time and risk | R4, Inventory (I3) |
| `R4:PurchaseRecommendation:{product_id}` | governed purchase recommendation | approval workflow, Inventory (in-transit) |
| `R5:ProcurementException:{po_id}` | reconciliation facts and exceptions | evaluation, Inventory exception handling |

Payload shapes are the models of the same names in
`backend/app/contracts/models.py`. See `SHARED_FIREBASE_CONFORMANCE.md` for
collection semantics, events and ownership.
