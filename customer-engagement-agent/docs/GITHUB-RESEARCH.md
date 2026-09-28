# GitHub / Engineering Research Notes

This implementation intentionally borrows **patterns**, not copied code, from public references.

## Patterns integrated

### 1. Local IndexedDB as the immediate source of truth
Reference: https://github.com/sab-khan/pwa-indexeddb-offline-demo

Useful pattern: write locally, make the UI deterministic from local persisted state, and keep database access outside components. In this project, Dexie is isolated in `apps/web/src/lib/db.ts` and repository operations live in `repository.ts`.

### 2. Small-shop offline-first workflow
Reference: https://github.com/ridzalap0112/offline-cashier

Useful pattern: SMEs need the app to remain functional without connectivity, not merely display a cached shell. C1–C5 therefore run entirely in local TypeScript and do not depend on an API call.

### 3. React + Vite + Tailwind + Dexie + Firebase combination
Reference: https://github.com/neomatsu/lista-compra

Useful pattern: Dexie provides local continuity while Firebase provides multi-device/shared cloud state. We retained Firebase because it is the agreed shared database for the 25-agent platform.

### 4. Feature-oriented modern Firebase client structure
Reference: https://github.com/fauzanriff/react-firebase-starter

Useful pattern: separate application/domain logic from Firebase bootstrapping and UI components. This reduces coupling when Customer Engagement is merged into the larger platform shell.

### 5. Offline POS sync-queue architecture
Reference: https://github.com/arnoldadero/offline-pos

Useful pattern: `user action -> IndexedDB -> UI -> queue -> cloud`. The project implements the same high-level data-flow idea while using Firestore as the cloud backend.

## Patterns deliberately not copied

- No separate database per mini-agent: C1–C5 are capabilities of one Customer Engagement Agent.
- No autonomous message sending: C4 creates a recommendation for human/platform action.
- No automatic price or stock mutations from C3: those belong to Pricing/Inventory.
- No open Firestore development rules in the production ruleset.
- No dependence on a paid AI API for core sentiment/segmentation; the MVP works offline with deterministic rules.

## Official references used to harden the design

- Firebase Security Rules: https://firebase.google.com/docs/rules
- Firestore rule structure: https://firebase.google.com/docs/firestore/security/rules-structure
- Firestore role-based access: https://firebase.google.com/docs/firestore/solutions/role-based-access
- Dexie best practices: https://dexie.org/docs/Tutorial/Best-Practices
- Dexie StorageManager notes: https://dexie.org/docs/StorageManager

## Future upgrades worth considering

1. Add platform-wide event schemas in a dedicated shared package once the other 24 top-level agents expose their contracts.
2. Add Firestore Emulator rules tests before production deployment.
3. Add a Cloud Function/queue consumer for cross-agent jobs that must continue when no client is open.
4. Add a pluggable AI sentiment adapter as an **optional online enhancer**, while keeping the local rules as a fallback.
5. Add a conflict policy per collection (append-only for events/transactions, server-authoritative for stock, versioned last-write/merge for profiles).
