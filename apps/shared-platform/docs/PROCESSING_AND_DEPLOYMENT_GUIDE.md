# Business Data Processing and Deployment Guide

## Purpose
The shared workspace now has one controlled processing flow. Business records are entered or imported first. Processing then reads the saved source records, runs the five business domains in dependency order, publishes current results, creates human-review items only where an action requires approval, and keeps prior runs for audit/history.

No synthetic business records are created by the processing flow.

## Processing order
1. **Demand** — D1 to D5 run against products, sales history, promotions and local events. The implementation uses the vendored Florah Demand source. D4 is converted to the shared DemandForecast contract before other domains consume it.
2. **Inventory** — I1 to I5 consume current stock, movements and the Demand forecast. Missing source records produce explicit unavailable/insufficient-evidence results rather than invented values.
3. **Procurement** — R1 to R5 use suppliers, quotes, delivery history, inventory needs and Demand evidence. Purchase recommendations are never converted into purchase orders without human approval.
4. **Pricing** — P1 to P5 use costs, margin floors, competitor observations, actual historical prices/quantities, stock risk and Demand evidence. Unsafe or incomplete evidence keeps P5 non-actionable.
5. **Customers** — C1 to C5 use the actual compiled Customer Engagement runtime with real customer, sales, product, stock and feedback context.

## Synchronisation rules
- Any CSV import, manual add or manual edit marks the workspace **Needs processing**.
- Only one processing run can own the business processing lease at a time.
- An abandoned processing lease can recover after 30 minutes instead of blocking the workspace forever.
- A processing run records the source-data timestamp it started from.
- If business data changes while a run is executing, that run is **not activated**. The previous successful results remain current and the workspace returns to **Needs processing**.
- Current dashboard/domain results are filtered to the active successful analysis run. Outputs from an interrupted/non-activated run do not become visible as current results.
- Successful processing atomically switches the active run only after all outputs have been persisted.
- Approved Pricing and Procurement actions update real source data and automatically mark the workspace **Needs processing** again so downstream areas can be recalculated.

## Human approval behaviour
- **P5 Pricing**: approval applies the governed product price only after the margin floor and maximum-change guardrails are rechecked server-side.
- **R4 Procurement**: approval creates a real purchase-order record. High-risk / high-value orders require a second reviewer.
- **C4 Customer action**: approval creates a ready work item. It is not falsely labelled executed because contacting a customer still requires a real operational action.
- Rejections are recorded but do not mutate business source data.
- Every decision is written to the approval log and audit history.

## Minimum real data to start
Products and sales are the minimum required to start processing. Other domains safely remain partial until their source records exist.

For useful operational results, add:
- Products
- Sales history
- Current stock counts
- Stock movements where available
- Suppliers and supplier quotes
- Supplier delivery/performance history when available
- Competitor price observations
- Customers only where the business has a legitimate customer/loyalty record
- Customer feedback where available

## Running locally
From `apps/shared-platform`:

```powershell
npm run dev
```

Open `http://localhost:5174`.

Workflow:
1. Open **Business data**.
2. Import CSV files or add/edit records manually.
3. Open **Process data**.
4. Check readiness.
5. Click **Process business data**.
6. Review results under Demand, Inventory, Procurement, Pricing and Customers.
7. Open **Approvals** for governed actions.
8. After an approved action changes source data, process again when the workspace shows new changes waiting.

## Production container
Build from the repository root, not from `apps/shared-platform`:

```bash
docker build -f apps/shared-platform/Dockerfile -t sme-shared-platform .
```

Required runtime environment:

```text
NODE_ENV=production
AUTH_MODE=firebase
FIREBASE_PROJECT_ID=sme-agent-platform-dev
BUSINESS_ID=dev-business
FIREBASE_SERVICE_ACCOUNT_JSON=<service account JSON secret>
FIREBASE_WEB_API_KEY=<Firebase web API key>
FIREBASE_WEB_AUTH_DOMAIN=<Firebase auth domain>
FIREBASE_WEB_APP_ID=<Firebase web app ID>
WEB_ORIGIN=https://<your deployed hostname>
```

Do not commit `FIREBASE_SERVICE_ACCOUNT_JSON` or a service-account file to the repository.

The application serves the built web interface and API from one service. `VITE_API_BASE_URL` is not required for this production layout because the browser uses `/api` on the same origin.

## Deployment checks
Before deploying:
- `npm run validate`
- `npm run validate:data`
- `npm run validate:process`
- confirm Firebase Auth login works
- confirm a user has access to the target business
- confirm the Firestore rules/indexes already deployed are the validated production rules
- confirm the deployment environment can run both Node.js and Python (the Dockerfile provides both)

After deploying:
1. Sign in.
2. Confirm Business data loads.
3. Confirm Process data reports the correct source-record counts.
4. Process a business with real records.
5. Confirm all five domain pages show the newly activated run.
6. Confirm an approval decision writes to Approval history.
7. Confirm Pricing/Procurement approvals mark the workspace as needing processing again.
8. Confirm a page refresh and application restart preserve all records/results.
