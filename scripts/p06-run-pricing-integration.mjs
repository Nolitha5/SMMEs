import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runPricingDomain } from "../integration/runtime/pricing.mjs";

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"..");
const reports=path.join(root,"reports");
fs.mkdirSync(reports,{recursive:true});
const policy=JSON.parse(fs.readFileSync(path.join(root,"architecture","pricing-policy.v1.json"),"utf8"));
const assert=(c,m)=>{if(!c)throw new Error(m);};
const now=new Date("2026-09-29T00:00:00Z");

const product={
  product_id:"SKU-PRICE-100",current_price:29.99,unit_cost:18.50,variable_fees_per_unit:.50,
  margin_floor_pct:.25,currency:"ZAR"
};
const competitors=[
  {store_name:"Store A",price:30.49,observed_at:"2026-09-28T18:00:00Z",source:"Tiyani-store-observation"},
  {store_name:"Store B",price:29.79,observed_at:"2026-09-28T19:00:00Z",source:"Tiyani-store-observation"},
  {store_name:"Store C",price:31.20,observed_at:"2026-09-28T20:00:00Z",source:"Tiyani-store-observation"},
  {store_name:"Stale Store",price:21.00,observed_at:"2026-09-20T12:00:00Z",source:"stale-test"}
];
const transactions=[
  {unit_price:35,qty:68},{unit_price:34,qty:72},{unit_price:33,qty:77},{unit_price:32,qty:83},
  {unit_price:31,qty:91},{unit_price:30,qty:100},{unit_price:29,qty:111},{unit_price:28.5,qty:118}
];
const d4={product_id:product.product_id,horizon_days:7,expected_qty:28,lower_bound:20,upper_bound:38,confidence:.86,drivers:["normal weekday demand"],generated_at:now.toISOString(),source_version:"demand-provisional-1.0"};
const i1={product_id:product.product_id,available_stock:85,stock_on_hand:90,reserved:5,damaged:0,in_transit:0,stock_status:"HEALTHY"};
const i4={product_id:product.product_id,risk_type:"EXCESS_STOCK",severity:"HIGH",available_stock:85,sales_velocity:.5,days_of_cover:170,confidence:.90,generated_at:now.toISOString(),formula_version:"I4-v1"};

const out=runPricingDomain({product,competitorObservations:competitors,transactions,d4,i1,i4,policy,now});
assert(out.p1.status==="OK","P1 did not produce market signal");
assert(out.p1.observations.length===3,"P1 stale observation was not removed");
assert(out.p2.status==="OK"&&out.p2.minimum_price>product.unit_cost,"P2 margin guard failed");
assert(out.p3.status==="ESTIMATED"&&out.p3.elasticity<0,"P3 elasticity estimate failed");
assert(out.p4.actionable===true&&out.p4.candidate_price>=out.p2.minimum_price,"P4 markdown guard failed");
assert(out.p5.status==="READY_FOR_REVIEW"&&out.p5.actionable===true,"P5 should produce human-review action");
assert(out.p5.proposed_price>=out.p2.minimum_price,"P5 crossed margin floor");
assert(out.p5.fairness_checks.includes("no_customer_specific_pricing"),"P5 fairness check missing");
assert(out.p5.fairness_checks.includes("human_approval_required"),"P5 approval guard missing");

// Fail-safe scenario: P3 cannot estimate from one transaction; P5 must remain DRAFT.
const fail=runPricingDomain({product,competitorObservations:competitors,transactions:[{unit_price:29.99,qty:1}],d4,i1,i4,policy,now});
assert(fail.p3.status==="INSUFFICIENT_DATA","P3 fail-safe did not trigger");
assert(fail.p5.status==="DRAFT"&&!fail.p5.actionable,"P5 must fail safe when P3 evidence is missing");

const report={generatedAt:now.toISOString(),passed:true,sourceBranch:"TIYANI-MANGANYI",completeEvidenceScenario:out,failSafeScenario:{p3:fail.p3,p5:fail.p5}};
fs.writeFileSync(path.join(reports,"p06-pricing-integration-report.json"),JSON.stringify(report,null,2));
console.log("Pricing P1 competitor monitor: PASS");
console.log(`Pricing P2 margin floor: R${out.p2.minimum_price.toFixed(2)}`);
console.log(`Pricing P3 elasticity: ${out.p3.elasticity} (confidence ${(out.p3.confidence*100).toFixed(0)}%)`);
console.log(`Pricing P4 candidate: R${out.p4.candidate_price.toFixed(2)} (${(out.p4.discount_pct*100).toFixed(1)}% markdown)`);
console.log(`Pricing P5 recommendation: R${out.p5.current_price.toFixed(2)} -> R${out.p5.proposed_price.toFixed(2)}; ${out.p5.status}`);
console.log("Pricing fairness/approval gate: PASS");
console.log("Pricing missing-evidence fail-safe: PASS");
console.log("P06_PRICING_INTEGRATION_OK");
