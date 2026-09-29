
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"..");

function run(script){
  const r=spawnSync(process.execPath,[path.join(root,"scripts",script)],{encoding:"utf8"});
  if(r.stdout) process.stdout.write(r.stdout);
  if(r.stderr) process.stderr.write(r.stderr);
  if(r.status!==0) process.exit(r.status ?? 1);
}
function assert(cond,msg){if(!cond){console.error(`FAIL: ${msg}`);process.exit(1);}}

run("p04-validate-architecture.mjs");
run("p05-run-core-integration.mjs");
run("p05-run-customer-integration.mjs");

const pricing=JSON.parse(fs.readFileSync(path.join(root,"architecture","pricing-integration-status.v1.json"),"utf8"));
assert(pricing.capabilities.P1.status==="partial-source-present","P1 status mismatch");
assert(pricing.capabilities.P2.status==="missing","P2 must remain explicitly missing");
assert(pricing.capabilities.P3.status==="missing","P3 must remain explicitly missing");
assert(pricing.capabilities.P4.status==="missing","P4 must remain explicitly missing");
assert(pricing.capabilities.P5.status==="partial-blocked","P5 must remain blocked until fairness/upstream guards are implemented");

const core=JSON.parse(fs.readFileSync(path.join(root,"reports","p05-core-integration-report.json"),"utf8"));
const customer=JSON.parse(fs.readFileSync(path.join(root,"reports","p05-customer-integration-report.json"),"utf8"));
assert(core.passed===true,"Core integration report failed");
assert(customer.passed===true && customer.actualCoreExecuted===true,"Customer actual core integration failed");

console.log("Pricing safety gate: PASS (P5 blocked until required guards exist)");
console.log("P05_AGENT_INTEGRATION_OK");
