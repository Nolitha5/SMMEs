# SME Agent Platform — Firebase Foundation Bootstrap

This bundle prevents manual collection creation in the Firebase console.

## What it does

- Targets the existing Firebase project `sme-agent-platform-dev`.
- Deploys Firestore rules and indexes with Firebase CLI.
- Creates the development business document.
- Creates platform schema metadata.
- Optionally creates the first owner membership document.
- Optionally seeds a tiny set of sample operational records.

## Important

Do not commit a service-account JSON key. `.gitignore` already excludes common key filenames.

## Setup

1. Install Node.js 20+.
2. Extract this folder and open it in VS Code.
3. Run:

```powershell
npm install
npx firebase login
```

4. In Firebase Console, go to Project settings > Service accounts > Generate new private key. Save it somewhere OUTSIDE the repository.
5. Copy `.env.example` to `.env` and set `GOOGLE_APPLICATION_CREDENTIALS` to the full Windows path of the downloaded JSON file.
6. Keep `SEED_SAMPLE_DATA=false` for the clean foundation.
7. If you already created your Auth user, paste that Firebase Auth UID into `OWNER_UID`. Otherwise leave it blank and rerun later.

## Bootstrap Firestore data

```powershell
npm run bootstrap
```

## Deploy Firestore rules + indexes

```powershell
npm run deploy:firestore
```

The rules are intentionally an integration-development baseline. After all agent repositories are audited, narrow permissions collection-by-collection according to authoritative ownership.
