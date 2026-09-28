# Start Here — Windows

## 1. Unzip the project

Keep the folder structure intact.

## 2. Open PowerShell in the project root

```powershell
cd "C:\PATH\TO\customer-engagement-agent"
```

## 3. Install packages

```powershell
npm install
```

## 4. Start the standalone test harness

```powershell
npm run dev
```

Open: `http://localhost:5173`

API health check: `http://localhost:8787/health`

This repository includes a standalone development interface so C1–C5 can be tested before the team's shared platform interface is merged. It is **not intended to become a second production interface**.

Sample records are opt-in through:

```text
VITE_ENABLE_DEMO_DATA=true
```

## 5. Test the workflow

1. Open **Overview**.
2. Click **Run C1–C5 cycle**.
3. Open **Customers** to see segment/risk/action outputs.
4. Open **Agent Lab** to inspect all five internal capability results for one customer.
5. Open **Feedback** and add a complaint or compliment.
6. Run C1–C5 again to see C5 influence C2/C4.
7. Open **Sync** to inspect the local-first queue.

## 6. Before committing to the team repository

Run:

```powershell
npm run integration:check
```

Then read:

```text
agent.manifest.json
docs/FINAL-PLATFORM-HANDOFF.md
docs/SHARED-FIREBASE-CONTRACT.md
docs/REPO-COMMIT-CHECKLIST.md
```

## 7. Shared Firebase integration

Do **not** create a separate production Firebase project for this agent. The final platform should supply one Firebase configuration, one Authentication system, one `businessId` context and one shared database.

For standalone testing only, copy `apps/web/.env.example` to `apps/web/.env.local`, add the shared Firebase configuration and set:

```text
VITE_ENABLE_FIREBASE=true
VITE_ENABLE_DEMO_DATA=false
VITE_BUSINESS_ID=<shared business id>
```

The final team repository should implement `CustomerEngagementDataPort` against its agreed Firestore schema. The current `firestore.rules` file is a reference for standalone development; merge the required rule fragments into the platform's central rules rather than replacing the team's rules file.
