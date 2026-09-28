# Repository Commit Checklist

Before pushing this agent to the team repository:

- Commit source code and docs; do not commit `node_modules`, `.env.local`, Firebase secrets or service-account JSON.
- Keep `agent.manifest.json` at the contribution root so the integration owner can inspect the contract quickly.
- Treat `apps/web` as a development/test harness, not the final shared UI.
- Treat `apps/api` as optional. The final coordinator can call the shared package directly if all agents run in one Node/TypeScript application.
- Preserve `packages/shared/src/agents/*`; these are the C1–C5 business rules.
- Preserve `packages/shared/src/integration/*`; this is the main platform seam.
- Do not create a separate production Firebase project for this agent.
- Do not replace another agent's authoritative sales, stock or pricing data during merge.
- Reconcile event names and collection schemas against the other agent repositories before wiring production listeners/triggers.

Recommended branch/PR description: `Customer Engagement Agent — C1-C5 core + integration contract`.
