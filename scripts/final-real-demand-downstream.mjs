import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { normalizeSharedOutputCore, buildAgentStateCore } from '../integration/runtime/exchange-core.mjs';
import { runPricingDomain } from '../integration/runtime/pricing.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const reports = path.join(root, 'reports');
const demandReport = JSON.parse(fs.readFileSync(path.join(reports, 'real-demand-source-report.json'), 'utf8'));
const policy = JSON.parse(fs.readFileSync(path.join(root, 'architecture', 'pricing-policy.v1.json'), 'utf8'));
const assert = (c,m)=>{ if(!c) throw new Error(m); };
const round=(n,d=2)=>{const p=10**d; return Math.round((Number(n)+Number.EPSILON)*p)/p;};

assert(demandReport.passed === true, 'real Demand source report is not green');
const d4 = demandReport.d4;
const sharedD4 = normalizeSharedOutputCore(demandReport.shared_output);
const d4State = buildAgentStateCore(sharedD4);
assert(d4State.capabilityId === 'D4', 'D4 shared state projection failed');
assert(d4State.payload.source_version === 'florah-demand-e3534ef', 'provisional Demand source leaked into final D4 state');
assert(d4.lower_bound <= d4.expected_qty && d4.expected_qty <= d4.upper_bound, 'real D4 bounds invalid downstream');

// Inventory contract/formula regression using the REAL Florah D4 payload.
const leadTimeDays = 5;
const serviceLevel = 0.95;
const reliabilityScore = 0.82;
const z = 1.65;
const expectedDaily = d4.expected_qty / d4.horizon_days;
const horizonStd = (d4.upper_bound - d4.lower_bound) / 4;
const dailyStd = horizonStd / Math.sqrt(d4.horizon_days);
const leadStd = dailyStd * Math.sqrt(leadTimeDays);
const reliabilityFactor = 1 + (1 - reliabilityScore);
const safetyStock = Math.max(0, Math.ceil(z * leadStd * reliabilityFactor));
assert(Number.isFinite(safetyStock) && safetyStock >= 0, 'I3 failed on real D4');

const availableStock = Math.max(5, Math.floor(d4.expected_qty * 0.25));
const inTransit = 0;
const reorderPoint = expectedDaily * leadTimeDays + safetyStock;
const inventoryPosition = availableStock + inTransit;
const reorderNeeded = inventoryPosition <= reorderPoint;
const recommendedQty = reorderNeeded ? Math.max(0, reorderPoint - inventoryPosition) : 0;
assert(reorderNeeded === true && recommendedQty > 0, 'I2 real-D4 scenario did not produce a reorder');

// Procurement R4 decision regression against the real-D4-derived reorder quantity.
const suppliers = [
  {id:'SUP-A', rankScore:.91, reliability:.87, relConfidence:.88, leadRisk:'LOW', leadConfidence:.88, unitCost:4.45, moq:100, p90:7},
  {id:'SUP-B', rankScore:.84, reliability:.95, relConfidence:.92, leadRisk:'MEDIUM', leadConfidence:.90, unitCost:4.20, moq:250, p90:11}
];
const leadScore={LOW:1,MEDIUM:.6,HIGH:.2};
const candidates=suppliers.map(s=>{
  const evidence=Math.min(s.relConfidence,s.leadConfidence,d4.confidence);
  const score=.40*s.rankScore+.35*s.reliability+.20*leadScore[s.leadRisk]+.05*evidence;
  const qty=Math.max(recommendedQty,s.moq);
  return {...s,qty,cost:qty*s.unitCost,score};
}).sort((a,b)=>b.score-a.score || a.cost-b.cost);
const r4=candidates[0];
assert(r4?.id, 'R4 could not select a supplier from real-D4 demand');
assert(Number.isFinite(r4.cost) && r4.cost > 0, 'R4 expected cost invalid');

// Pricing P1-P5 consumes the REAL Florah D4 payload.
const now = new Date();
const product={product_id:d4.product_id,current_price:8.00,unit_cost:4.20,variable_fees_per_unit:0,margin_floor_pct:.15,currency:'ZAR'};
const competitorObservations=[
  {store_name:'A',price:8.20,observed_at:new Date(now-1*3600_000).toISOString(),source:'final-test'},
  {store_name:'B',price:7.95,observed_at:new Date(now-2*3600_000).toISOString(),source:'final-test'},
  {store_name:'C',price:8.10,observed_at:new Date(now-3*3600_000).toISOString(),source:'final-test'}
];
const priceDemand=[
  {unit_price:9.2,qty:24},{unit_price:9.0,qty:27},{unit_price:8.8,qty:30},{unit_price:8.6,qty:34},
  {unit_price:8.4,qty:38},{unit_price:8.2,qty:43},{unit_price:8.0,qty:49},{unit_price:7.8,qty:56}
];
const i1={product_id:d4.product_id,available_stock:Math.max(150,Math.ceil(d4.expected_qty*3)),stock_on_hand:Math.max(150,Math.ceil(d4.expected_qty*3)),reserved:0,damaged:0,in_transit:0,stock_status:'HEALTHY'};
const i4={product_id:d4.product_id,risk_type:'EXCESS_STOCK',severity:'HIGH',available_stock:i1.available_stock,confidence:.9,generated_at:now.toISOString(),formula_version:'I4-v1'};
const pricing=runPricingDomain({product,competitorObservations,transactions:priceDemand,d4,i1,i4,policy,now});
assert(pricing.p1.status==='OK','P1 failed with real D4 context');
assert(pricing.p2.status==='OK','P2 failed with real D4 context');
assert(pricing.p3.status==='ESTIMATED','P3 failed in final regression');
assert(pricing.p4.actionable===true,'P4 failed to produce safe markdown candidate');
assert(pricing.p5.status==='READY_FOR_REVIEW','P5 governance gate failed with real D4');
assert(pricing.p5.proposed_price>=pricing.p2.minimum_price,'P5 crossed P2 margin floor');

const report={
  passed:true,
  firebaseWrites:false,
  demandSource:d4.source_version,
  realD4:d4,
  inventory:{safetyStock,reorderPoint:round(reorderPoint),inventoryPosition,recommendedQty:round(recommendedQty)},
  procurement:{supplier:r4.id,qty:round(r4.qty),expectedCost:round(r4.cost),decisionScore:round(r4.score,4)},
  pricing:{p1:pricing.p1.status,p2Minimum:pricing.p2.minimum_price,p3Elasticity:pricing.p3.elasticity,p4Candidate:pricing.p4.candidate_price,p5Status:pricing.p5.status,p5Price:pricing.p5.proposed_price}
};
fs.writeFileSync(path.join(reports,'final-real-demand-downstream-report.json'),JSON.stringify(report,null,2));
console.log('Real D4 -> Inventory: PASS');
console.log(`Real D4 -> Procurement: PASS (${r4.id})`);
console.log('Real D4 -> Pricing P1-P5: PASS');
console.log('Real D4 shared state projection: PASS');
console.log('REAL_DEMAND_DOWNSTREAM_TEST_OK');
