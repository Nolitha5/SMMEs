FIREBASE FOUNDATION P01 SECURITY PATCH

Why this patch exists:
The original integration-development wildcard rule also matched /members/{userId}.
Firestore combines overlapping allow rules with OR semantics, so a broad allow can
weaken a more specific rule. This replacement limits the wildcard to an explicit
operational collection allow-list and gives /members and /platformMeta separate rules.

Apply:
1. Close VS Code's firestore.rules tab if it is open.
2. Copy this firestore.rules into the root of firebase-foundation-bootstrap.
3. Replace the existing firestore.rules when Windows asks.
4. Do NOT run npm run deploy:firestore yet. Continue the guided setup first.
