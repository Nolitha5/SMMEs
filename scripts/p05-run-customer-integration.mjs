
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { demoData, DEMO_BUSINESS_ID } from "../vendor/customer-engagement-shared/dist/fixtures/demo.js";
import { executeCustomerEngagementCycle } from "../vendor/customer-engagement-shared/dist/integration/runtime.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const reportDir = path.join(root, "reports");
fs.mkdirSync(reportDir, { recursive: true });

const compatibility = JSON.parse(fs.readFileSync(path.join(root,"architecture","compatibility-map.v1.json"),"utf8"));
const eventMap = compatibility.customerEngagement.internalEventToBoundary;

function assert(cond,msg){ if(!cond) throw new Error(msg); }
function outputType(agentId){
  return {C1:"CustomerSegment",C2:"RetentionRisk",C3:"PromotionRecommendation",C4:"CustomerAction",C5:"FeedbackInsight"}[agentId];
}
function scoreFor(piece){
  if(piece.agentId==="C1") return Math.max(0,Math.min(1,Number(piece.score||0)/100));
  if(piece.agentId==="C2") return Math.max(0,Math.min(1,Number(piece.riskScore||0)/100));
  if(piece.agentId==="C3") return Math.max(0,Math.min(1,Number(piece.score||0)/100));
  if(piece.agentId==="C5") return Math.max(0,Math.min(1,Math.abs(Number(piece.sentimentScore||0))));
  return piece.priority==="high"?0.9:piece.priority==="medium"?0.6:0.3;
}
function riskFor(piece){
  if(piece.agentId==="C2") return piece.riskBand==="critical"||piece.riskBand==="high"?"HIGH":piece.riskBand==="medium"?"MEDIUM":"LOW";
  if(piece.agentId==="C4") return piece.priority==="high"?"HIGH":piece.priority==="medium"?"MEDIUM":"LOW";
  return "LOW";
}

const now = new Date("2026-09-29T00:00:00Z");
const data = demoData(now);
const memory = {insights:[],events:[]};

const port = {
  async readCustomers(){ return data.customers; },
  async readTransactions(){ return data.transactions; },
  async readProducts(){ return data.products; },
  async readFeedback(){ return data.feedback; },
  async writeInsights(_businessId, rows){ memory.insights.push(...rows); },
  async publishEvents(_businessId, rows){ memory.events.push(...rows); }
};

const result = await executeCustomerEngagementCycle(port, DEMO_BUSINESS_ID, now.toISOString());
assert(result.customerCount===6,"Expected 6 demo customers");
assert(result.results.length===6,"Expected results for all demo customers");
assert(memory.insights.length===30,"C1-C5 should create 30 insight projections");
assert(memory.events.length===30,"C1-C5 should create 30 events");

const canonicalOutputs=[];
const canonicalState={};
const recommendations=[];

for(const customer of result.results){
  const pieces=[customer.segment,customer.churn,customer.promotion,customer.nextAction,customer.feedback];
  for(const piece of pieces){
    const ot=outputType(piece.agentId);
    const outputId=`${piece.agentId}-${customer.customerId}-p05`;
    const env={
      output_id:outputId,
      agent_id:piece.agentId,
      domain:"customer-engagement",
      output_type:ot,
      entity_type:"customer",
      entity_id:customer.customerId,
      payload:piece,
      input_refs:[],
      confidence:scoreFor(piece),
      risk_level:riskFor(piece),
      generated_at:now.toISOString(),
      expires_at:null,
      model_or_rule_version:"cea-0.1.0",
      run_id:`run-${outputId}`,
      schema_version:"1.0",
      state_id:`${piece.agentId}:${ot}:${customer.customerId}`
    };
    canonicalOutputs.push(env);
    canonicalState[env.state_id]=env;

    // C4 is the final customer-facing action. C3 remains a candidate feeding C4.
    if(piece.agentId==="C4" && piece.action!=="no-action"){
      recommendations.push({
        recommendation_id:`rec-${customer.customerId}-C4`,
        source_output_id:outputId,
        agent_id:"C4",
        domain:"customer-engagement",
        output_type:"CustomerAction",
        entity_type:"customer",
        entity_id:customer.customerId,
        action:piece,
        confidence:env.confidence,
        risk_level:env.risk_level,
        status:"READY_FOR_REVIEW",
        created_at:now.toISOString(),
        expires_at:null,
        schema_version:"1.0"
      });
    }
  }
}

const versionedEvents=memory.events.map(e=>({
  ...e,
  name:eventMap[e.name] || e.name
}));
assert(versionedEvents.every(e=>e.name.endsWith(".v1")),"Customer events must map to versioned platform names");
assert(canonicalOutputs.length===30,"Expected 30 canonical outputs");
assert(Object.keys(canonicalState).length===30,"Expected 30 canonical state projections");
assert(recommendations.length>0,"Expected at least one C4 review action");

const report={
  generatedAt:now.toISOString(),
  passed:true,
  actualCoreExecuted:true,
  customerCount:result.customerCount,
  canonicalOutputCount:canonicalOutputs.length,
  canonicalStateCount:Object.keys(canonicalState).length,
  legacyInsightProjectionCount:memory.insights.length,
  versionedEventCount:versionedEvents.length,
  recommendationCount:recommendations.length,
  sample:{
    output:canonicalOutputs[0],
    event:versionedEvents[0],
    recommendation:recommendations[0]
  }
};
fs.writeFileSync(path.join(reportDir,"p05-customer-integration-report.json"),JSON.stringify(report,null,2));
console.log(`Customer C1-C5 actual core: PASS`);
console.log(`Canonical outputs: ${canonicalOutputs.length}`);
console.log(`Canonical state projections: ${Object.keys(canonicalState).length}`);
console.log(`Versioned events: ${versionedEvents.length}`);
console.log(`C4 review actions: ${recommendations.length}`);
