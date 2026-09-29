# Integrated SME Operations Platform

This branch is the deployable, integrated 25-agent SME operations platform.

## Application root

`apps/shared-platform`

The application combines the React/Node shared platform with the real Python Demand runtime and the integrated Inventory, Procurement, Pricing and Customer Engagement processing flows.

## What is included

- Business data CSV import, manual add and edit
- Real Demand D1-D5 processing
- Inventory I1-I5 processing
- Procurement R1-R5 processing
- Pricing P1-P5 processing
- Customer C1-C5 processing
- Human approval workflow
- Firebase Authentication + Firestore integration
- Processing locks, stale-run recovery and data-change isolation
- Production Dockerfile with Node.js + Python
- Production validation scripts

## Before deploying

From `apps/shared-platform` run:

```bash
npm install
npm run validate:data
npm run validate:process
npm run validate
npm run validate:production
```

All four commands must pass.

## Secrets

No Firebase Admin service-account JSON or `.env` file is stored in this repository.

For local development, keep credentials outside the repository. For a hosting provider, configure server credentials using that provider's secret/environment-variable system. Never commit private keys to GitHub.

Firebase Web SDK configuration is client-side configuration and is separate from Firebase Admin credentials.

## Free deployment

The branch can be cloned by any teammate and adapted to a free host that supports the required Node.js + Python runtime/container. The Docker application root is `apps/shared-platform`.

For a no-billing presentation, the complete validated runtime can also be run locally and exposed through a secure Cloudflare Tunnel.
