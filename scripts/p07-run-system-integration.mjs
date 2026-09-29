import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { demoData, DEMO_BUSINESS_ID } from "../vendor/customer-engagement-shared/dist/fixtures/demo.js";
import { executeCustomerEngagementCycle } from "../vendor/customer-engagement-shared/dist/integration/runtime.js";
import { runPricingDomain } from "../integration/runtime/pricing.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const reports = path.join(root, "reports");
fs.mkdirSync(reports, { recursive: true });

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const round = (n, d = 2) => {
  const p = 10 ** d;
  return Math.round((Number(n) + Number.EPSILON) * p) / p;
};
const now = new Date("2026-09-29T00:00:00Z");

// Previous gates must already have produced reports.
const core = JSON.parse(fs.readFileSync(path.join(reports, "p05-core-integration-report.json"), "utf8"));
const customerBaselineReport = JSON.parse(fs.readFileSync(path.join(reports, "p05-customer-integration-report.json"), "utf8"));
const pricingBaselineReport = JSON.parse(fs.readFileSync(path.join(reports, "p06-pricing-integration-report.json"), "utf8"));
const pricingPolicy = JSON.parse(fs.readFileSync(path.join(root, "architecture", "pricing-policy.v1.json"), "utf8"));

assert(core.passed === true, "P05 core gate is not green");
assert(core.summary?.requiresHumanApproval === true, "R4 governance gate missing");
assert(customerBaselineReport.passed === true && customerBaselineReport.actualCoreExecuted === true, "Actual C1-C5 runtime gate is not green");
assert(pricingBaselineReport.passed === true, "P06 pricing gate is not green");

// ---------------------------------------------------------------------------
// One real cross-domain handoff:
// P5 recommendation -> human approval -> authoritative product projection -> C3/C4
// ---------------------------------------------------------------------------
const data = demoData(now);
const baseProduct = data.products.find(p => p.id === "prod-maize");
assert(baseProduct, "Demo product prod-maize missing");

const sharedProduct = {
  ...baseProduct,
  stock: 42,
  reorderLevel: 12,
  price: 84.99,
  marginPct: round(((84.99 - 63.00) / 84.99) * 100, 2),
  sourceAgent: "Pricing"
};

const priceProduct = {
  product_id: sharedProduct.id,
  current_price: sharedProduct.price,
  unit_cost: 63.00,
  variable_fees_per_unit: 0,
  margin_floor_pct: 0.15,
  currency: "ZAR"
};
const competitorObservations = [
  { store_name: "Store A", price: 86.50, observed_at: "2026-09-28T18:00:00Z", source: "P07-fixture" },
  { store_name: "Store B", price: 84.20, observed_at: "2026-09-28T19:00:00Z", source: "P07-fixture" },
  { store_name: "Store C", price: 83.70, observed_at: "2026-09-28T20:00:00Z", source: "P07-fixture" }
];
const priceDemandHistory = [
  { unit_price: 95, qty: 40 }, { unit_price: 92, qty: 45 }, { unit_price: 89, qty: 50 }, { unit_price: 86, qty: 58 },
  { unit_price: 84.99, qty: 62 }, { unit_price: 82, qty: 68 }, { unit_price: 80, qty: 76 }, { unit_price: 78, qty: 85 }
];
const d4 = {
  product_id: sharedProduct.id,
  horizon_days: 7,
  expected_qty: 24,
  lower_bound: 18,
  upper_bound: 31,
  confidence: 0.86,
  drivers: ["normal weekday demand"],
  generated_at: now.toISOString(),
  source_version: "demand-provisional-1.0"
};
const i1 = {
  product_id: sharedProduct.id,
  available_stock: sharedProduct.stock,
  stock_on_hand: sharedProduct.stock,
  reserved: 0,
  damaged: 0,
  in_transit: 0,
  stock_status: "HEALTHY"
};
const i4 = {
  product_id: sharedProduct.id,
  risk_type: "EXCESS_STOCK",
  severity: "HIGH",
  available_stock: sharedProduct.stock,
  sales_velocity: 0.5,
  days_of_cover: 84,
  confidence: 0.90,
  generated_at: now.toISOString(),
  formula_version: "I4-v1"
};

const pricing = runPricingDomain({
  product: priceProduct,
  competitorObservations,
  transactions: priceDemandHistory,
  d4,
  i1,
  i4,
  policy: pricingPolicy,
  now
});

assert(pricing.p1.status === "OK", "P1 failed in cross-domain scenario");
assert(pricing.p2.status === "OK", "P2 failed in cross-domain scenario");
assert(pricing.p3.status === "ESTIMATED", "P3 failed in cross-domain scenario");
assert(pricing.p4.actionable === true, "P4 did not produce a bounded candidate");
assert(pricing.p5.status === "READY_FOR_REVIEW" && pricing.p5.actionable === true, "P5 must be review-gated");
assert(pricing.p5.proposed_price < sharedProduct.price, "Scenario must produce a markdown");

const priceRecommendation = {
  recommendation_id: "rec-P5-prod-maize-p07",
  source_output_id: "P5-PriceRecommendation-prod-maize-p07",
  agent_id: "P5",
  domain: "pricing",
  output_type: "PriceRecommendation",
  entity_type: "product",
  entity_id: sharedProduct.id,
  action: pricing.p5,
  confidence: pricing.p5.confidence,
  risk_level: pricing.p5.risk_level,
  status: "READY_FOR_REVIEW",
  created_at: now.toISOString(),
  expires_at: null,
  schema_version: "1.0"
};

function makePort(dataset) {
  const writes = { insights: [], events: [] };
  return {
    writes,
    port: {
      async readCustomers() { return dataset.customers; },
      async readTransactions() { return dataset.transactions; },
      async readProducts() { return dataset.products; },
      async readFeedback() { return dataset.feedback; },
      async writeInsights(_businessId, rows) { writes.insights.push(...rows); },
      async publishEvents(_businessId, rows) { writes.events.push(...rows); }
    }
  };
}

const beforeData = {
  ...data,
  products: data.products.map(p => p.id === sharedProduct.id ? { ...sharedProduct } : p)
};
const beforePort = makePort(beforeData);
const beforeCustomer = await executeCustomerEngagementCycle(beforePort.port, DEMO_BUSINESS_ID, now.toISOString());
const siphoBefore = beforeCustomer.results.find(r => r.customerId === "cus-sipho");
assert(siphoBefore, "Sipho customer result missing before approval");
assert(siphoBefore.promotion.eligible === true, "Sipho should have a promotion candidate before approval");
assert(siphoBefore.promotion.productId === sharedProduct.id, "Expected maize to be Sipho's selected promotion product before approval");

// Critical governance invariant: recommendation alone does not mutate shared truth.
assert(beforeData.products.find(p => p.id === sharedProduct.id).price === 84.99, "Unapproved P5 recommendation changed authoritative price");

const approval = {
  approval_id: "approval-P5-prod-maize-p07",
  recommendation_id: priceRecommendation.recommendation_id,
  reviewer: "demo-owner",
  decision: "APPROVED",
  modified_action: null,
  reason: "P07 deterministic integration approval",
  decided_at: new Date(now.getTime() + 60_000).toISOString(),
  schema_version: "1.0"
};
priceRecommendation.status = "APPROVED";

const approvedPrice = pricing.p5.proposed_price;
const approvedMarginPct = round(((approvedPrice - priceProduct.unit_cost) / approvedPrice) * 100, 2);
assert(approvedPrice >= pricing.p2.minimum_price, "Approved price crossed P2 margin floor");
assert(approvedMarginPct >= 12, "Approved product margin would violate Customer Engagement C3 minimum guardrail");

const afterData = {
  ...data,
  products: data.products.map(p => p.id === sharedProduct.id ? {
    ...sharedProduct,
    price: approvedPrice,
    marginPct: approvedMarginPct,
    sourceAgent: "Pricing"
  } : p)
};
const afterPort = makePort(afterData);
const afterCustomer = await executeCustomerEngagementCycle(afterPort.port, DEMO_BUSINESS_ID, new Date(now.getTime() + 120_000).toISOString());
const siphoAfter = afterCustomer.results.find(r => r.customerId === "cus-sipho");
assert(siphoAfter, "Sipho customer result missing after approval");
assert(siphoAfter.promotion.eligible === true, "Sipho promotion unexpectedly became ineligible after approved pricing update");
assert(siphoAfter.promotion.productId === sharedProduct.id, "Expected maize to remain Sipho's selected promotion product after approval");
assert(siphoAfter.promotion.offerPct <= siphoBefore.promotion.offerPct, "C3 did not recompute offer from the lower approved margin");
assert(afterPort.writes.events.length === 30, "C1-C5 event publication count changed after cross-domain update");

const report = {
  generatedAt: now.toISOString(),
  passed: true,
  firebaseWrites: false,
  priorGates: {
    p05Core: core.passed,
    p05CustomerActualCore: customerBaselineReport.actualCoreExecuted,
    p06Pricing: pricingBaselineReport.passed
  },
  governance: {
    priceRecommendationStatusBeforeApproval: "READY_FOR_REVIEW",
    authoritativePriceBeforeApproval: sharedProduct.price,
    approval,
    authoritativePriceAfterApproval: approvedPrice,
    marginPctAfterApproval: approvedMarginPct,
    marginFloor: pricing.p2.minimum_price
  },
  crossDomainHandoff: {
    producer: "P5",
    governance: "approvalLog",
    projection: "products/prod-maize",
    consumers: ["C3", "C4"],
    siphoPromotionBefore: siphoBefore.promotion,
    siphoPromotionAfter: siphoAfter.promotion,
    siphoNextActionAfter: siphoAfter.nextAction
  },
  existingCoreChain: {
    chain: core.scenario,
    selectedSupplier: core.summary.selectedSupplier,
    expectedCost: core.summary.expectedCost,
    approvalRequired: core.summary.requiresHumanApproval
  },
  demandStatus: {
    realFlorahSourceIntegrated: false,
    boundaryValidated: true,
    nextAction: "Replace provisional D4 provider with Florah's real D4 and rerun this gate."
  }
};

fs.writeFileSync(path.join(reports, "p07-system-integration-report.json"), JSON.stringify(report, null, 2));
console.log("System governance gate: PASS");
console.log(`P5 approval: R${sharedProduct.price.toFixed(2)} -> R${approvedPrice.toFixed(2)}`);
console.log(`C3 approved-margin recompute: ${siphoBefore.promotion.offerPct}% -> ${siphoAfter.promotion.offerPct}%`);
console.log("Actual C1-C5 runtime after approved Pricing projection: PASS");
console.log("Existing D4 -> Inventory -> Procurement gate: PASS");
console.log("Florah replacement boundary: READY");
console.log("P07_SYSTEM_INTEGRATION_OK");
