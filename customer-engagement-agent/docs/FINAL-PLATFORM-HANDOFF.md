# Final Platform Handoff — Customer Engagement

## What this repository contributes

This repository contributes **one top-level Customer Engagement Agent**. C1–C5 are internal capabilities, not five independent platform agents.

The production integration boundary is the package `@cea/shared`. The React app in `apps/web` is a **standalone development harness** for testing this agent before the team's final shared interface arrives. Do not copy its navigation/auth shell into the final application unless the team explicitly chooses to reuse it.

## Final architecture

```text
Shared platform UI
  -> shared Firebase Authentication
  -> shared platform context (businessId, user/role)
  -> shared Firestore database
  -> platform adapters/event coordinator
       -> Customer Engagement runtime (@cea/shared)
            -> C1 Segmentation
            -> C2 Retention Risk
            -> C3 Promotion Recommender
            -> C4 Next-Best-Action
            -> C5 Feedback & Sentiment
       -> other top-level agents
```

## The key merge rule

**Do not make Customer Engagement create a second Firebase project, a second login system, or a second production interface.**

The final repository should supply the Firebase configuration once. Customer Engagement receives data through `CustomerEngagementDataPort` and publishes only its owned insights/events through the same port.

## Integration API

```ts
import {
  executeCustomerEngagementCycle,
  CUSTOMER_ENGAGEMENT_MANIFEST,
  type CustomerEngagementDataPort
} from '@cea/shared';

const port: CustomerEngagementDataPort = platformFirebaseAdapter;
const result = await executeCustomerEngagementCycle(port, businessId);
```

Only the adapter knows the final Firestore collection paths. C1–C5 do not know or care whether the team's final schema is `businesses/{businessId}/transactions`, `businesses/{businessId}/sales/transactions`, or another agreed structure.

## What must be reconciled when the other agents arrive

1. Exact collection names and document schemas.
2. Exact agent IDs used by the coordinator.
3. Exact event names/envelope used by the team.
4. Ownership rules: which agent is authoritative for each field.
5. Authentication/member roles from the shared platform.
6. Whether the coordinator invokes Customer Engagement in-process, through an API, or from a Firebase/Cloud Function trigger.
7. Final UI routes/cards/pages for Customer Engagement.

The files `agent.manifest.json` and `packages/shared/src/integration/*` were added specifically to make this reconciliation localized instead of forcing edits throughout C1–C5.

## Data ownership

Customer Engagement may read sales, inventory and pricing state, but it must not silently mutate those agents' authoritative records. It writes customer-engagement insights and shared events. Other agents then decide how to act on those events according to their ownership boundaries.

## Offline behavior

The current development harness keeps Dexie/IndexedDB for offline testing. The final platform may keep this adapter or replace it with the platform's own offline layer. The core C1–C5 package is independent of Dexie.

## Files the merger should start with

- `agent.manifest.json`
- `packages/shared/src/integration/manifest.ts`
- `packages/shared/src/integration/runtime.ts`
- `docs/SHARED-FIREBASE-CONTRACT.md`
- `docs/INTEGRATION-CONTRACT.md`

Then inspect C1–C5 under `packages/shared/src/agents/`.
