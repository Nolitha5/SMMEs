import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const assert = (condition, message) => {
  if (!condition) {
    console.error(`FAIL: ${message}`);
    process.exit(1);
  }
};
const run = script => {
  const result = spawnSync(process.execPath, [path.join(root, "scripts", script)], { encoding: "utf8" });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.status !== 0) process.exit(result.status ?? 1);
};

run("p06-validate-pricing.mjs");
for (const file of [
  "architecture/p07-system-integration-gate.v1.json",
  "docs/P07-SYSTEM-INTEGRATION-GATE.md",
  "scripts/p07-run-system-integration.mjs"
]) {
  assert(fs.existsSync(path.join(root, file)), `missing ${file}`);
}
run("p07-run-system-integration.mjs");
const report = JSON.parse(fs.readFileSync(path.join(root, "reports", "p07-system-integration-report.json"), "utf8"));
assert(report.passed === true, "P07 system report failed");
assert(report.firebaseWrites === false, "P07 must remain local-only");
assert(report.governance.priceRecommendationStatusBeforeApproval === "READY_FOR_REVIEW", "P5 was not approval gated");
assert(report.governance.authoritativePriceAfterApproval >= report.governance.marginFloor, "approved price is below margin floor");
assert(report.demandStatus.boundaryValidated === true, "Florah replacement boundary not validated");
console.log("P07_SYSTEM_INTEGRATION_VALIDATED");
