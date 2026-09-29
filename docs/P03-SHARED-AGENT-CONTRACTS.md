# P03 — Shared Agent Contracts

This phase defines the Firestore-native interoperability boundary for all 25 top-level agents.

## Contract collections

- `agentEvents`: facts that happened and can trigger other agents.
- `agentInsights`: derived intelligence tied to a business entity.
- `agentActions`: requested/recommended work with a lifecycle.
- `auditLogs`: append-only operational/security records.

Every record is business-scoped. `agentEvents` and `agentActions` require `correlationId` and `idempotencyKey` so retries can be safe and workflows can be traced end-to-end.

## Event naming

Use `<domain>.<entity>.<verb>.v<major>`.

Examples:

- `sales.transaction.recorded.v1`
- `inventory.stock.changed.v1`
- `customer.feedback.received.v1`
- `customer.retention-risk.changed.v1`

## Delivery semantics

The platform is designed for at-least-once-compatible processing. Consumers must treat `idempotencyKey` as the deduplication key and must not assume an event can only be delivered once.

## Ownership

`ownershipRegistry` records whether a collection is platform-shared or still pending repository audit. Domain ownership for customers/products/inventory/transactions/orders/suppliers/feedback/promotions is deliberately not finalized until all agent repositories are inspected.

## Security boundary

P03 Firestore rules validate the shape and business scope of the four shared contract collections. They do not yet prove that `sourceAgent` cryptographically matches the runtime agent identity. That final identity/authorization layer must be added after the repositories and deployment model are audited.
