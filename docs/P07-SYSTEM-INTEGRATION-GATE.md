# P07 — Full Local System Integration Gate

This closes the **available-agent portion of Priority 2** without touching live Firebase.

The gate proves:

- the existing P04 architecture remains valid;
- D4 → Inventory → Procurement remains valid;
- the actual C1–C5 Customer Engagement package still runs;
- Pricing P1–P5 remains guarded and fail-safe;
- a P5 recommendation cannot change authoritative product price before approval;
- after an APPROVED governance decision, the resulting product projection can be consumed by Customer Engagement;
- Customer Engagement recalculates its promotion recommendation from the approved price/margin state;
- the Florah D4 boundary remains replaceable without downstream rewrites.

## Important

This is still a **local integration harness**. It performs no Firestore writes and no Firebase deployment.

Florah's real D1–D5 source remains the only missing real domain implementation. When it arrives, D4 is inserted behind the existing Demand adapter and this same gate is rerun.
