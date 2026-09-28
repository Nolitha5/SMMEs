# Customer Engagement Cross-Agent Integration Contract

## Reads from the shared database

| Source | Data consumed | Used by |
|---|---|---|
| Sales Agent | transactions, recency, spend, basket items | C1, C2, C3, C4 |
| Inventory Agent | stock, reorder level, active products | C3, C4 |
| Pricing / Finance | margin %, optional campaign limits | C3 |
| Customer records | consent, profile, last visit | C1–C5 |
| Customer feedback | message, channel, timestamp | C2, C5 |

## Writes to the shared database

| Collection | Owner | Purpose |
|---|---|---|
| `insights` | Customer Engagement | segment, risk, promotion, sentiment, next action |
| `events` | Shared event stream | lets other top-level agents react to engagement changes |
| `syncAudit` | Platform sync layer | operational trace for synced offline writes |

## Important ownership boundary

Customer Engagement can recommend a promotion based on stock and margin, but it does not alter inventory quantity or authoritative pricing. It emits a recommendation/event that the appropriate top-level agent can consume.

## Event examples

- `customer.segment.updated`
- `customer.retention.risk.changed`
- `customer.promotion.recommended`
- `customer.feedback.insight.created`
- `customer.next_action.recommended`

Each event contains `businessId`, `producer`, `targetAgents`, `entityId`, `createdAt`, and a typed payload.
