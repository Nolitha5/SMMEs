# Architecture

## Core rule

**Customer Engagement is one top-level agent. C1–C5 are internal capabilities.** They share one runtime, one local persistence layer, one coordinator, and one shared Firebase tenant namespace.

## Runtime flow

```text
Business UI
   |
   v
Local Repository (Dexie / IndexedDB) <----> React live queries
   |
   +--> Customer Engagement Coordinator
   |      C1 Segment
   |      C5 Feedback/Sentiment
   |      C2 Retention Risk
   |      C3 Promotion Recommendation
   |      C4 Next-Best-Action
   |
   +--> Agent Events / Insights
   |
   +--> Sync Queue ---- when online ----> Shared Firebase / Firestore
                                             |
                                             +--> Inventory Agent
                                             +--> Sales Agent
                                             +--> Pricing Agent
                                             +--> Finance Agent
                                             +--> Other platform agents
```

## Why C5 runs before C2 in the coordinator

The UI labels remain C1–C5, but orchestration order is dependency-based. Recent negative feedback can increase retention risk, so feedback analysis is calculated before the churn/retention score. C4 runs last because it consumes the outputs from C1, C2, C3, and C5.

## Local-first write policy

1. Validate input.
2. Persist locally.
3. Add a sync-queue item.
4. Publish a local event.
5. Update UI immediately.
6. If online and Firebase is configured, flush queued items.
7. On failure, keep the queue item and increment retry metadata.

## Cross-agent rules

- Inventory remains the source of truth for stock/reorder levels.
- Sales remains the source of truth for completed transactions.
- Customer Engagement may read those records but must not silently rewrite them.
- Customer Engagement owns engagement insights and customer-engagement events.
- Promotions are recommendations, not automatic price changes.
- C4 recommendations require a human action in this MVP; no autonomous messaging is sent.

## Privacy and safety

- Marketing recommendations respect `consentMarketing`.
- Firebase rules are business-scoped and role-based.
- Local demo data is synthetic.
- The Firestore client rules are not treated as filters; queries must include the business path.
- If a server later uses Firebase Admin SDK, IAM and server-side authorization are still required because Admin SDK access bypasses Firestore Security Rules.
