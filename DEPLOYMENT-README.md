# Integrated SME Operations Platform

The `integrated-platform` branch contains the deployable integrated 25-agent SME operations platform.

## Application

Application source: `apps/shared-platform`

The platform combines React, Node.js, the real Python Demand runtime, and the integrated Inventory, Procurement, Pricing, and Customer Engagement processing flows.

## Included

- Business data CSV import, manual add, and edit
- Real Demand D1-D5 processing
- Inventory I1-I5 processing
- Procurement R1-R5 processing
- Pricing P1-P5 processing
- Customer C1-C5 processing
- Human approval workflow
- Firebase Authentication and Firestore integration
- Processing locks, stale-run recovery, and data-change isolation
- Production Node.js + Python Docker image
- Production validation scripts

## Validate before deployment

From `apps/shared-platform`:

```bash
npm install
npm run validate:data
npm run validate:process
npm run validate
npm run validate:production
```

All commands must pass.

## Docker deployment

Use the repository root as the Docker build context. The root `Dockerfile` is the canonical production image.

From the repository root:

```bash
docker build -t sme-shared-platform .
```

If a hosting service requires an explicit Dockerfile path, use:

`apps/shared-platform/Dockerfile`

but keep the build context at the repository root because the image requires `architecture/`, `vendor/florah-demand/`, and `vendor/customer-engagement-shared/`.

The production container listens on port `8080` by default.

## Configuration

Use the hosting provider's environment-variable and secret-management interface. Do not commit `.env` files, Firebase Admin service-account JSON files, private keys, or certificates.

Use Firebase authentication in production and configure the Firebase project and browser app settings using the values from your Firebase project. The committed `.env.example` files are templates only.

## Free hosting

Any teammate can clone the `integrated-platform` branch and deploy it to a free host that supports the required Node.js + Python container/runtime. For a no-billing presentation, the validated production runtime can also be run locally and exposed with a secure Cloudflare Tunnel.
