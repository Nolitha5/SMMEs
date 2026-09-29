P03 SHARED AGENT CONTRACTS PATCH

Copy these files/folders into your existing firebase-foundation-bootstrap folder:
  package.json
  firestore.rules
  scripts/p03-create-contracts.mjs
  scripts/p03-verify-contracts.mjs
  scripts/p03-validate-contract-files.mjs
  contracts/
  docs/P03-SHARED-AGENT-CONTRACTS.md

DO NOT replace .env.

Run, in order:
  npm run p03:validate-local
  npm run p03:contracts
  npm run deploy:firestore
  npm run p03:verify

Expected final line:
  P03 verification PASSED.

This patch creates metadata/registries only. It does not create fake operational data.
