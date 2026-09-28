# API Surface

Base: `/api/v1`

## System

- `GET /health`
- `GET /ready`
- `GET /me`
- `GET /dashboard`
- `GET /audit`

## Agents

- `GET /agents/status`
- `POST /agents/{R1|R2|R3|R4|R5}/run`
- `POST /procurement/recommend/{product_id}` — orchestrates R1, R2, R3 and R4
- `POST /procurement/reconcile/{po_id}` — runs R5
- `POST /procurement/close/{po_id}/{reconciliation_id}` — closes accepted reconciliation and writes supplier performance feedback

## Recommendations and approval

- `GET /recommendations?agent_id=&status=&risk=`
- `GET /recommendations/{id}`
- `POST /recommendations/{id}/decision`
- `POST /recommendations/{id}/execute` — creates PO only for approved/modified R4 recommendations

Decision body:

```json
{
  "decision": "APPROVED",
  "reason": "Stock risk confirmed"
}
```

For `MODIFIED`, add `modified_action`.

Every recommendation record carries the shared-envelope fields `output_id`,
`source_output_id`, `domain`, `input_refs`, `run_id`, `schema_version` alongside
the previously documented fields.

## Shared exchange layer

- `GET /outputs/{output_type}/{entity_id}` — latest valid `agent_state`
  projection (404 if absent, expired or schema-invalid). Works for Procurement
  outputs and for upstream contracts, e.g. `/outputs/ReorderNeed/SKU-100`.
- `GET /outputs/{output_type}/{entity_id}/history` — `agent_outputs` history,
  newest first.
- `GET /runs/{run_id}` — one `agent_runs` execution trace.
- `GET /audit` — the `system_events` stream, newest first.

## Data

- `GET /data/{collection}` — any collection below, plus read-only access to the
  exchange and governance collections (`agent_outputs`, `agent_state`,
  `agent_runs`, `system_events`, `agent_recommendations`, `approval_log`,
  `outcomes`) and shared context (`products`, `inventory_snapshots`,
  `inventory_movements`).
- `PUT /data/{collection}` — operational collections only. Returns 404 for any
  exchange/governance collection: those are written solely by the backend's
  own services.
- `POST /imports/{collection}` multipart CSV

Operational collections (Procurement is the canonical writer):

- suppliers
- supplier_quotes
- supplier_performance
- purchase_orders
- goods_receipts
- invoices

Upstream contract imports (published into `agent_outputs` + `agent_state` on
the owning agent's behalf — no Procurement collection is created):

- demand_forecasts → D4 `DemandForecast`
- inventory_positions → I1 `InventoryPosition`
- reorder_needs → I2 `ReorderNeed`
- safety_stock_targets → I3 `SafetyStockTarget`

Importing or upserting a goods receipt emits `goods.receipt.recorded`; an
invoice emits `invoice.received`.

## Supplier intelligence

- `GET /suppliers/{supplier_id}/scorecard` — runs R2 and R3 and returns current supplier profile.
