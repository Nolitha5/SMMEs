# P05 — Priority 2 Agent Integration

This patch runs locally only. It does not write to Firebase.

## What now executes

### Core cross-domain scenario
A deterministic local scenario executes the current contract/formula boundary:

`D4 -> I1/I3 -> I2 -> R4`

- D4 uses the provisional canonical DemandForecast boundary.
- I3 calculation mirrors the current Thobeka I3 formula.
- I2 calculation mirrors the current Thobeka reorder-point formula.
- Inventory outputs are adapted to the exact contract fields Noosrat's R4 expects.
- R4 supplier selection mirrors the current Noosrat scoring and risk logic.
- R1/R2/R3 are supplied as valid evidence fixtures in this scenario; their own algorithms are not duplicated.

### Customer Engagement
The patch includes and executes the **actual compiled C1-C5 shared package** from the integration-ready Customer Engagement agent.

It then projects those real C1-C5 results into:
- `agentOutputs`
- `agentState`
- versioned `agentEvents`
- `agentRecommendations` for C4 customer-facing actions

Legacy `agentInsights` remains only a compatibility/UI projection.

### Pricing
Tiyani's current source is guarded rather than misrepresented:
- P1 has useful source material (scraping/store price observations).
- P2 margin guard is missing.
- P3 elasticity is missing; existing price-trend regression is not relabeled as elasticity.
- P4 markdown/promotion pricing is missing.
- P5 deal advice is partial and is blocked from becoming a canonical executable PriceRecommendation until D4/I1/I4/P2/P3/P4 and fairness controls exist.

## Firebase
No Firebase migration or deployment occurs in P05.

The next work inside Priority 2 is to replace local integration boundaries with repository adapters around the actual Inventory, Procurement and Pricing source trees. Florah's real D4 replaces the provisional D4 provider when her source is available.
