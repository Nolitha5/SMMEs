# Shared Firebase Contract

Customer Engagement is prepared for **one shared Firebase project** owned by the final platform.

## Logical records required

The final Firestore layout may change, but the adapter must be able to provide these logical entities:

| Logical entity | Authority | Customer Engagement access |
|---|---|---|
| Customer | Shared/platform customer domain | Read; profile/consent input |
| Transaction | Sales Agent | Read only |
| Product stock | Inventory Agent | Read only |
| Product price/margin | Pricing/Finance Agent | Read only |
| Feedback | Customer Engagement/shared intake | Read; feedback intake may write |
| Engagement insight | Customer Engagement Agent | Write |
| Platform event | Shared coordinator/event stream | Publish |

## Required tenant key

Every record crossing the agent boundary must be scoped by `businessId`. The runtime rejects mixed-business batches.

## Adapter, not hard-coded paths

The final platform should implement `CustomerEngagementDataPort` once against its agreed Firestore schema. Do not spread Firestore path strings through C1–C5.

Example only:

```text
businesses/{businessId}/customers/{customerId}
businesses/{businessId}/transactions/{transactionId}
businesses/{businessId}/products/{productId}
businesses/{businessId}/feedback/{feedbackId}
businesses/{businessId}/insights/{insightId}
businesses/{businessId}/events/{eventId}
```

These paths are a reference layout, not a requirement. When the team's repository arrives, the adapter will be aligned to the real schema.

## Security

- Firebase Auth is supplied by the shared platform.
- Security Rules must validate membership/role and business scope.
- Server-side Firebase Admin code is protected by IAM and does not rely on client Security Rules.
- Final rules belong in the platform repository; this agent's `firestore.rules` is a standalone development reference only.
- Security Rules should be tested with the Firebase Local Emulator Suite before deployment.

## Offline

Firestore can maintain a persistent web cache, while this development harness also uses Dexie for an explicit local queue. At merge time, keep one clear platform offline strategy to avoid two competing sync authorities.
