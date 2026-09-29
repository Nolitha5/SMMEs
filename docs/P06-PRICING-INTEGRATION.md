# P06 — Pricing P1-P5 Integration

P06 completes the **integration baseline** for the Pricing domain without pretending that Tiyani's standalone Flask application already contained all five agreed platform capabilities.

## Source preserved from Tiyani

- multi-store/competitor observed prices;
- price history and statistical deal/trend context;
- target-price/watch concepts remain non-authoritative context.

## Canonical capabilities now wired

- **P1 Competitor Price Monitor** — normalizes fresh competitor observations and expires stale observations.
- **P2 Margin Guard** — calculates the explicit minimum selling price required by unit cost + variable fees + margin floor.
- **P3 Demand Elasticity** — uses quantity-vs-price history only when there is enough variation/data; otherwise returns insufficient evidence.
- **P4 Markdown/Promotion Candidate** — reacts to I4 stock risk and D4 demand but cannot cross P2's minimum price.
- **P5 Price Recommendation & Fairness Gate** — combines D4, I1/I4 and P1-P4; blocks event-based surge pricing, customer-specific pricing, margin violations and unapproved execution.

## Critical rule

P5 is always a human-review commercial action. Missing/unreliable P2/P3/P4 evidence leaves P5 `DRAFT` and non-actionable.

## Scope

This is still a local integration harness. It does **not** deploy Firestore, change Firebase security rules, or write production prices.
