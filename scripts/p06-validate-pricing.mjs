import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"..");
const assert=(c,m)=>{if(!c){console.error(`FAIL: ${m}`);process.exit(1);}};
function run(script){const r=spawnSync(process.execPath,[path.join(root,"scripts",script)],{encoding:"utf8"});if(r.stdout)process.stdout.write(r.stdout);if(r.stderr)process.stderr.write(r.stderr);if(r.status!==0)process.exit(r.status??1);}

run("p05-validate-integration.mjs");
for(const f of [
  "architecture/pricing-integration-status.v2.json","architecture/pricing-policy.v1.json","architecture/pricing-contract-map.v1.json",
  "integration/runtime/pricing.mjs","contracts/competitor-price-signal.v1.schema.json","contracts/allowed-price-range.v1.schema.json",
  "contracts/elasticity-estimate.v1.schema.json","contracts/promo-price-candidate.v1.schema.json","contracts/price-recommendation.v1.schema.json"
]) assert(fs.existsSync(path.join(root,f)),`missing ${f}`);
const status=JSON.parse(fs.readFileSync(path.join(root,"architecture","pricing-integration-status.v2.json"),"utf8"));
for(const id of ["P1","P2","P3","P4","P5"]) assert(status.capabilities[id],`pricing status missing ${id}`);
assert(status.capabilities.P5.approvalRequired===true,"P5 must require approval");
run("p06-run-pricing-integration.mjs");
const report=JSON.parse(fs.readFileSync(path.join(root,"reports","p06-pricing-integration-report.json"),"utf8"));
assert(report.passed===true,"pricing integration report failed");
assert(report.completeEvidenceScenario.p5.status==="READY_FOR_REVIEW","P5 action is not review-gated");
assert(report.failSafeScenario.p5.status==="DRAFT","P5 fail-safe did not remain DRAFT");
console.log("P06_PRICING_INTEGRATION_VALIDATED");
