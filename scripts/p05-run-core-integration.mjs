
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const reportDir = path.join(root, "reports");
fs.mkdirSync(reportDir, { recursive: true });

const now = new Date();
const iso = now.toISOString();

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}
function round(n, d=4) {
  const p = 10 ** d;
  return Math.round((n + Number.EPSILON) * p) / p;
}
function stateId(agentId, outputType, entityId) {
  return `${agentId}:${outputType}:${entityId}`;
}
function envelope({agentId, domain, outputType, entityType, entityId, payload, confidence, risk="LOW", version="1.0"}) {
  const outputId = `${agentId}-${entityId}-${Date.now()}-${Math.random().toString(16).slice(2,8)}`;
  return {
    output_id: outputId,
    agent_id: agentId,
    domain,
    output_type: outputType,
    entity_type: entityType,
    entity_id: entityId,
    payload,
    input_refs: [],
    confidence,
    risk_level: risk,
    generated_at: iso,
    expires_at: null,
    model_or_rule_version: version,
    run_id: `run-${outputId}`,
    schema_version: "1.0",
    state_id: stateId(agentId, outputType, entityId)
  };
}

// Provisional canonical D4 boundary.
const d4 = {
  product_id: "SKU-100",
  horizon_days: 7,
  expected_qty: 310,
  lower_bound: 270,
  upper_bound: 355,
  confidence: 0.86,
  drivers: ["weekend uplift", "local event"],
  generated_at: iso,
  source_version: "demand-provisional-1.0"
};
assert(d4.lower_bound <= d4.expected_qty && d4.expected_qty <= d4.upper_bound, "D4 bounds invalid");
const d4Out = envelope({
  agentId:"D4", domain:"demand", outputType:"DemandForecast",
  entityType:"product", entityId:d4.product_id, payload:d4, confidence:d4.confidence,
  version:d4.source_version
});

// I1 contract sample. This is current inventory truth, not a reorder decision.
const i1Native = {
  product_id:"SKU-100",
  sku:"SKU-100",
  product_name:"Demo Staple",
  category:"Staples",
  store_id:"STORE-001",
  snapshot_timestamp:iso,
  stock_on_hand:95,
  reserved:10,
  damaged:0,
  in_transit:0,
  available_stock:85,
  stock_status:"LOW",
  days_of_supply:1.92,
  needs_attention:true,
  forecast_7d_demand:d4.expected_qty,
  forecast_confidence:d4.confidence,
  forecast_source:d4.source_version
};
const i1Procurement = {
  product_id:i1Native.product_id,
  on_hand:i1Native.stock_on_hand,
  on_order:i1Native.in_transit,
  allocated:i1Native.reserved,
  available:i1Native.available_stock,
  generated_at:iso,
  source_version:"I1-v1"
};
const i1Out = envelope({
  agentId:"I1", domain:"inventory", outputType:"InventoryPosition",
  entityType:"product", entityId:i1Native.product_id, payload:i1Procurement,
  confidence:1, version:"I1-v1"
});

// I3 exact current formula from Thobeka source.
const leadTimeDays = 5;
const reliabilityScore = 0.82;
const serviceLevel = 0.95;
const z = 1.65;
const expectedDaily = d4.expected_qty / d4.horizon_days;
const horizonStd = (d4.upper_bound - d4.lower_bound) / 4;
const dailyStd = horizonStd / Math.sqrt(d4.horizon_days);
const leadTimeDemandStd = dailyStd * Math.sqrt(leadTimeDays);
const reliabilityFactor = 1 + (1 - Math.max(0, Math.min(1, reliabilityScore)));
const rawSafetyStock = z * leadTimeDemandStd * reliabilityFactor;
const safetyStock = Math.max(0, Math.ceil(rawSafetyStock));

const i3Native = {
  product_id:d4.product_id,
  safety_stock:safetyStock,
  expected_daily_demand:round(expectedDaily),
  forecast_uncertainty:round(dailyStd),
  lead_time_days:leadTimeDays,
  reliability_score:reliabilityScore,
  reliability_factor:round(reliabilityFactor),
  service_level:serviceLevel,
  z_score:z,
  raw_safety_stock:round(rawSafetyStock),
  confidence:"HIGH",
  reason:"P05 local integration scenario",
  formula_version:"I3-v1",
  generated_at:iso
};
const i3Procurement = {
  product_id:i3Native.product_id,
  safety_stock:i3Native.safety_stock,
  service_level:i3Native.service_level,
  lead_time_days:i3Native.lead_time_days,
  generated_at:i3Native.generated_at,
  source_version:i3Native.formula_version
};
const i3Out = envelope({
  agentId:"I3", domain:"inventory", outputType:"SafetyStockTarget",
  entityType:"product", entityId:d4.product_id, payload:i3Procurement,
  confidence:0.90, version:"I3-v1"
});
i3Out.input_refs = [d4Out.output_id, i1Out.output_id];

// I2 exact current formula from Thobeka source.
const avgDailyDemand = d4.expected_qty / d4.horizon_days;
const reorderPoint = avgDailyDemand * leadTimeDays + safetyStock;
const inventoryPosition = i1Native.available_stock + i1Native.in_transit;
const reorderNeeded = inventoryPosition <= reorderPoint;
const suggestedQty = reorderNeeded ? Math.max(0, reorderPoint - inventoryPosition) : 0;

const i2Native = {
  product_id:d4.product_id,
  inventory_position:round(inventoryPosition,2),
  reorder_point:round(reorderPoint,4),
  reorder_needed:reorderNeeded,
  suggested_reorder_qty:round(suggestedQty,2),
  generated_at:iso,
  source_version:"I2-v1.0-basic-rop"
};
const i2Procurement = {
  product_id:i2Native.product_id,
  reorder_point:i2Native.reorder_point,
  projected_position:i2Native.inventory_position,
  reorder_needed:i2Native.reorder_needed,
  recommended_qty:i2Native.suggested_reorder_qty,
  generated_at:i2Native.generated_at,
  source_version:i2Native.source_version
};
const i2Out = envelope({
  agentId:"I2", domain:"inventory", outputType:"ReorderNeed",
  entityType:"product", entityId:d4.product_id, payload:i2Procurement,
  confidence:0.92, version:i2Native.source_version
});
i2Out.input_refs = [d4Out.output_id, i1Out.output_id, i3Out.output_id];

// Valid Procurement evidence fixtures matching Noosrat contract shapes.
const supplierComparison = {
  product_id:d4.product_id,
  requested_qty:i2Procurement.recommended_qty,
  ranked_suppliers:[
    {
      supplier_id:"SUP-A", supplier_name:"Supplier A", score:0.91, rank:1,
      unit_cost:18.50, moq:100, quoted_lead_time_days:5, payment_terms_days:30,
      score_breakdown:{cost:0.88,moq_fit:1,lead_time:1,payment_terms:0.8,coverage:1},
      warnings:[]
    },
    {
      supplier_id:"SUP-B", supplier_name:"Supplier B", score:0.84, rank:2,
      unit_cost:17.80, moq:250, quoted_lead_time_days:8, payment_terms_days:30,
      score_breakdown:{cost:1,moq_fit:0.7,lead_time:0.7,payment_terms:0.8,coverage:1},
      warnings:["MOQ exceeds requested quantity"]
    }
  ],
  generated_at:iso
};
const reliability = {
  "SUP-A": {supplier_id:"SUP-A",score:0.87,on_time_rate:0.9,fill_rate:0.92,defect_rate:0.02,invoice_accuracy:0.96,sample_size:10,confidence:0.88},
  "SUP-B": {supplier_id:"SUP-B",score:0.95,on_time_rate:0.96,fill_rate:0.97,defect_rate:0.01,invoice_accuracy:0.98,sample_size:12,confidence:0.92}
};
const leadRisk = {
  "SUP-A": {supplier_id:"SUP-A",median_days:5,expected_days:5.4,p90_days:7,variability_days:1.2,delay_rate:0.10,risk:"LOW",sample_size:10,confidence:0.88},
  "SUP-B": {supplier_id:"SUP-B",median_days:8,expected_days:8.7,p90_days:11,variability_days:2.4,delay_rate:0.22,risk:"MEDIUM",sample_size:12,confidence:0.90}
};

// R4 exact scoring/guardrail logic from current Noosrat source.
assert(i2Procurement.reorder_needed && i2Procurement.recommended_qty > 0, "Scenario must require reorder");
const leadScore = {LOW:1.0, MEDIUM:0.6, HIGH:0.2};
const candidates = supplierComparison.ranked_suppliers.map(rank => {
  const rel = reliability[rank.supplier_id];
  const lead = leadRisk[rank.supplier_id];
  const evidenceConf = Math.min(rel.confidence, lead.confidence, d4.confidence);
  let decisionScore = 0.40 * rank.score + 0.35 * rel.score + 0.20 * leadScore[lead.risk] + 0.05 * evidenceConf;
  const qty = Math.max(i2Procurement.recommended_qty, rank.moq);
  if ((rank.warnings || []).some(w => w.toLowerCase().includes("available quantity"))) decisionScore *= 0.75;
  return {rank, rel, lead, qty, expectedCost:qty*rank.unit_cost, decisionScore};
});
candidates.sort((a,b) => b.decisionScore - a.decisionScore || a.expectedCost - b.expectedCost);
const chosen = candidates[0];

let risk = "LOW";
if (chosen.lead.risk === "HIGH" || chosen.rel.score < 0.55 || d4.confidence < 0.45) risk = "HIGH";
else if (chosen.lead.risk === "MEDIUM" || chosen.rel.score < 0.75 || d4.confidence < 0.70) risk = "MEDIUM";
const secondReview = chosen.expectedCost >= 25000 || risk === "HIGH";
if (secondReview) risk = "HIGH";

const r4 = {
  supplier_id:chosen.rank.supplier_id,
  product_id:d4.product_id,
  qty:round(chosen.qty,2),
  unit_cost:chosen.rank.unit_cost,
  expected_cost:round(chosen.expectedCost,2),
  eta_days:chosen.lead.p90_days,
  supplier_score:chosen.rank.score,
  reliability_score:chosen.rel.score,
  lead_time_risk:chosen.lead.risk,
  risk,
  currency:"ZAR",
  decision_score:round(chosen.decisionScore,4),
  alternatives:candidates.slice(1,4).map(c => ({
    supplier_id:c.rank.supplier_id,
    qty:round(c.qty,2),
    expected_cost:round(c.expectedCost,2),
    decision_score:round(c.decisionScore,4),
    lead_time_risk:c.lead.risk,
    reliability_score:c.rel.score
  }))
};
const r4Out = envelope({
  agentId:"R4", domain:"procurement", outputType:"PurchaseRecommendation",
  entityType:"product", entityId:d4.product_id, payload:r4,
  confidence:Math.min(0.96, 0.50 + 0.25*chosen.rel.confidence + 0.15*chosen.lead.confidence + 0.10*d4.confidence),
  risk, version:"1.0.0-r4"
});
r4Out.input_refs = [
  i2Out.output_id, i3Out.output_id, d4Out.output_id,
  "R1:SupplierComparison:SKU-100", "R2:SupplierReliabilityScore:SUP-A", "R3:LeadTimeRisk:SUP-A"
];

assert(r4.supplier_id === "SUP-A", "R4 should select Supplier A in the deterministic scenario");
assert(r4.expected_cost < 25000, "Scenario unexpectedly requires second review");
assert([d4Out,i1Out,i3Out,i2Out,r4Out].every(x => x.state_id === stateId(x.agent_id,x.output_type,x.entity_id)), "state_id contract failed");

const report = {
  generatedAt:iso,
  scenario:"D4 -> I1/I3 -> I2 -> R4",
  passed:true,
  d4:d4Out,
  i1:i1Out,
  i3:i3Out,
  i2:i2Out,
  r4:r4Out,
  summary:{
    safetyStock,
    reorderPoint:round(reorderPoint,2),
    projectedPosition:inventoryPosition,
    recommendedQty:i2Procurement.recommended_qty,
    selectedSupplier:r4.supplier_id,
    expectedCost:r4.expected_cost,
    r4Risk:r4.risk,
    requiresHumanApproval:true
  }
};
fs.writeFileSync(path.join(reportDir,"p05-core-integration-report.json"), JSON.stringify(report,null,2));
console.log(`Core chain: PASS`);
console.log(`Safety stock: ${safetyStock}`);
console.log(`Reorder qty: ${i2Procurement.recommended_qty}`);
console.log(`R4 supplier: ${r4.supplier_id}`);
console.log(`R4 expected cost: R${r4.expected_cost}`);
console.log(`R4 approval gate: READY_FOR_REVIEW`);
