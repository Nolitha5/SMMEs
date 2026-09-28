# Customer Engagement Agent — SME / Spaza Offline-First MVP

A working MVP of **one Customer Engagement Agent** with five coordinated internal capabilities:

- **C1 — Customer Segmentation**
- **C2 — At-Risk / Churn Retention**
- **C3 — Promotion Recommender**
- **C4 — Next-Best-Action**
- **C5 — Feedback & Sentiment**

It is designed to plug into the larger 25-agent SME/spaza platform. It does **not** create isolated infrastructure for each mini-agent. All capabilities share the same local data layer, shared contracts, shared event stream, and shared Firebase business namespace.

## Stack

- React 19 + Vite + TypeScript
- Tailwind CSS
- Dexie / IndexedDB for offline-first local persistence
- Firebase Authentication + Cloud Firestore for shared cloud state
- Vite PWA plugin for installable/offline app shell
- Node.js + Express + TypeScript API for optional online orchestration
- Vitest for deterministic agent-engine tests

## Run locally

```powershell
cd "PATH\TO\customer-engagement-agent"
npm install
npm run dev
```

Open `http://localhost:5173`. The API runs on `http://localhost:8787`.

The app starts in **Local Demo Mode** and seeds realistic sample SME/spaza data, so Firebase is **not required** to test the complete C1–C5 workflow.

## Run quality gates

```powershell
npm run quality
```

## Enable Firebase

1. Create one Firebase project for the whole 25-agent platform.
2. Enable Authentication and Cloud Firestore.
3. Copy `.env.example` to `apps/web/.env.local` and fill in your Firebase web configuration.
4. Set `VITE_ENABLE_FIREBASE=true`.
5. Create a membership document using the Firebase Console or trusted server/admin process:

```text
businesses/{businessId}/members/{firebaseUid}
{ role: "owner" }
```

6. Deploy the included Firestore rules:

```powershell
npx firebase-tools deploy --only firestore:rules,firestore:indexes
```

## Shared Firestore shape

```text
businesses/{businessId}
  members/{uid}
  customers/{customerId}
  transactions/{transactionId}
  products/{productId}
  feedback/{feedbackId}
  insights/{insightId}
  events/{eventId}
  syncAudit/{syncId}
```

All top-level platform agents can exchange governed data through the same `businesses/{businessId}` namespace. Customer Engagement consumes Sales/Inventory-style records and publishes engagement insights/events for other agents.

## Offline-first contract

Every user-facing write lands in IndexedDB first. Cloud sync is a secondary operation. The app therefore remains useful when a township/spaza connection drops and can retry queued writes when connectivity returns.

## GitHub / technical references used

The architecture was informed by reusable patterns from public projects and official documentation, including:

- `sab-khan/pwa-indexeddb-offline-demo` — local event log + deterministic rebuild pattern
- `ridzalap0112/offline-cashier` — small-shop offline-first React + Dexie pattern
- `neomatsu/lista-compra` — React/Vite/Tailwind/Dexie + Firebase sync approach
- `fauzanriff/react-firebase-starter` — feature-oriented React/Firebase structure
- Firebase Security Rules and role-based access documentation
- Dexie transaction and offline-storage guidance

See `docs/ARCHITECTURE.md` and `docs/INTEGRATION-CONTRACT.md`.

## Team-repository / final-platform integration

This repository is now prepared to be merged into the team's single-interface, single-Firebase platform. **`apps/web` is a development harness, not a requirement for the final interface.** The reusable production seam is `@cea/shared`, especially `CustomerEngagementDataPort` and `executeCustomerEngagementCycle()`.

Start the merge review with [`agent.manifest.json`](./agent.manifest.json) and [`docs/FINAL-PLATFORM-HANDOFF.md`](./docs/FINAL-PLATFORM-HANDOFF.md). The exact final Firestore paths and cross-agent event envelope remain deliberately adapter-driven until the other agent repositories and shared interface are available.
