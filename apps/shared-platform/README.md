# SME Operations — Shared Application

One interface for the five-domain / 25-capability SME operations platform.

## Design rules

- Mostly white workspace.
- Chicago Bears dark navy `#0B162A`.
- Chicago Bears orange `#C83803`.
- White `#FFFFFF`.
- Compact typography, restrained rounding and strong separators.
- No fake charts, no decorative "AI" widgets and no controls without a backend action.

## Functional scope

- Overview based on live Firestore exchange/governance data.
- Approval queue with real APPROVE / REJECT writes through the trusted API.
- Shared event activity.
- Five domain workspaces.
- Live capability/run status.
- Current canonical state output inspection.
- Firebase email/password sign-in when client config is supplied.
- Strict disconnected state: architecture is visible, operational data is never fabricated.

## Local development

Copy `.env.example` to `.env`.

For design/integration work without Firebase credentials:

- keep `AUTH_MODE=local`
- keep `VITE_AUTH_MODE=local`

This mode does not fabricate data. It exposes the real architecture registry while Firestore-backed areas remain empty.

For live Firebase:

- set `GOOGLE_APPLICATION_CREDENTIALS` to the service-account file outside the repository;
- set the `VITE_FIREBASE_*` values;
- set `AUTH_MODE=firebase`;
- set `VITE_AUTH_MODE=firebase`.

Run:

```powershell
npm install
npm run validate
npm run dev
```

Open `http://localhost:5174`.

## Processing real business data
Use **Business data** to import/add/edit source records, then **Process data** to run the five-domain analysis. See `docs/PROCESSING_AND_DEPLOYMENT_GUIDE.md` for the dependency flow, synchronisation rules, approval behaviour and production deployment requirements.
