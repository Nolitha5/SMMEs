# Staging Deployment

The deployment follows the supplied stack: React/Vite/Tailwind, FastAPI/Python, Firebase Authentication + Firestore + Storage, Google Cloud background/deployment services and GitHub Actions.

## Target topology

- Firebase Authentication — manager/admin access
- Cloud Firestore — operational records and recommendation/audit state
- Firebase Storage — restricted import/evidence files
- Cloud Run — FastAPI backend
- Firebase Hosting — React frontend
- GitHub Actions — CI and manual staging deployment
- Cloud Scheduler — optional scheduled supplier-score refresh or reconciliation scan

## Prerequisites

1. Google Cloud/Firebase project.
2. Firestore enabled in Native mode.
3. Firebase Authentication Email/Password provider enabled.
4. Firebase Storage enabled.
5. Artifact Registry repository named `procurement`.
6. Cloud Run, Cloud Build and Artifact Registry APIs enabled.
7. GitHub workload identity federation or equivalent service-account authentication.

## Backend environment

Set Cloud Run:

```text
APP_ENV=staging
AUTH_MODE=firebase
REPOSITORY_BACKEND=firestore
FIREBASE_PROJECT_ID=<project-id>
CORS_ORIGINS=https://<firebase-hosting-domain>
MAX_PO_VALUE_WITHOUT_SECOND_REVIEW=25000
```

Cloud Run should use a service account with least-privilege Firestore access. Prefer workload identity; do not commit service-account JSON.

## Firebase user role

The Firestore rules expect an authenticated token custom claim `role` equal to one of:

- `admin`
- `owner_manager`
- `procurement_manager`

The backend uses the same claim for protected procurement actions.

## GitHub secrets

Required by `.github/workflows/deploy-staging.yml`:

```text
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
GCP_PROJECT_ID
GCP_REGION
STAGING_WEB_ORIGIN
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_STORAGE_BUCKET
VITE_FIREBASE_APP_ID
FIREBASE_TOKEN
```

For long-lived production use, replace `FIREBASE_TOKEN` with a service-account/OIDC-based Firebase deployment approach.

## First staging load

Use authenticated CSV imports or an admin-only bootstrap process to load suppliers, quotes, supplier performance and external I2/I3/D4 fixtures. Do not expose `/demo/bootstrap` to untrusted users; it remains manager-protected and should be disabled or removed in production hardening if unnecessary.

## Staging acceptance checklist

1. `/api/v1/health` is 200.
2. `/api/v1/ready` reports Firestore.
3. Firebase unauthenticated users cannot access protected endpoints/data.
4. R1 ranks valid supplier quotes and ignores expired offers.
5. R2/R3 scorecards reflect supplier history.
6. R4 returns `READY_FOR_REVIEW` for a genuine reorder.
7. R4 refuses stale or missing I2/I3/D4 data.
8. Manager approves R4; PO creation is impossible before approval.
9. Repeated execute requests do not create duplicate POs.
10. R5 clean match closes successfully.
11. R5 mismatch requires review.
12. PO close creates supplier performance feedback.
13. Audit events contain manager identity and linked record IDs.
14. Frontend build is served by Firebase Hosting and works at mobile/desktop widths.
15. CI is green before staging is declared complete.
