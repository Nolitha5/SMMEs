import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { FieldValue, Timestamp } from 'firebase-admin/firestore';
import { ROOT } from '../config.mjs';
import { getFirebaseServices } from '../firebase.mjs';
import { normalizedCapabilities } from '../architecture.mjs';
import { clamp, highestRisk, insufficient, makeResult, parseDate, round, stableId } from './common.mjs';
import { buildSupplierEvidence, runProcurementDomain } from './procurement-runtime.mjs';
import { runInventoryDomain } from './inventory-runtime.mjs';
import { runPricingDomain } from './pricing-runtime.mjs';
import { runCustomerDomain } from './customer-runtime.mjs';

const FOUNDATION = path.resolve(ROOT, '..', '..');
const demandScript = path.join(ROOT, 'server', 'process', 'demand_runner.py');
const pricingPolicy = JSON.parse(fs.readFileSync(path.join(ROOT, 'server', 'process', 'pricing-policy.json'), 'utf8'));
const PROCESSING_LEASE_MS = 30 * 60 * 1000;

const SOURCE_COLLECTIONS = [
  'products','transactions','promotions','localEvents','inventorySnapshots','inventoryMovements','competitorPrices',
  'suppliers','supplierQuotes','supplierPerformance','purchaseOrders','goodsReceipts','invoices','customers','feedback','customerInteractions'
];

function services() {
  const { db, error } = getFirebaseServices();
  if (!db) { const err = new Error(error?.message || 'Firestore is unavailable.'); err.code = 'FIREBASE_UNAVAILABLE'; throw err; }
  return db;
}

function clean(value) {
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value === 'object') {
    if (value instanceof Timestamp || typeof value.toDate === 'function') return value.toDate().toISOString();
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, clean(v)]));
  }
  return value;
}

function firestoreSafe(value, inArray = false) {
  if (value === undefined) return inArray ? null : undefined;
  if (value === null) return null;
  if (typeof value === 'number' && !Number.isFinite(value)) return null;
  if (typeof value === 'bigint') return String(value);
  if (value instanceof Date) return value.toISOString();
  if (value instanceof Timestamp || (value && typeof value.toDate === 'function')) return value;
  if (Array.isArray(value)) return value.map((item) => firestoreSafe(item, true));
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, item]) => [key, firestoreSafe(item, false)])
        .filter(([, item]) => item !== undefined)
    );
  }
  return value;
}

function safeSet(batch, ref, value, options) {
  const cleanValue = firestoreSafe(value);
  if (options) batch.set(ref, cleanValue, options);
  else batch.set(ref, cleanValue);
}

async function readCollection(businessId, name) {
  const snap = await services().collection(`businesses/${businessId}/${name}`).get();
  return snap.docs.map((doc) => ({ id: doc.id, ...clean(doc.data()) }));
}

async function readBusinessSnapshot(businessId) {
  const db = services();
  const business = await db.doc(`businesses/${businessId}`).get();
  const sourceEntries = await Promise.all(SOURCE_COLLECTIONS.map(async (name) => [name, await readCollection(businessId, name)]));
  return { business: business.exists ? clean(business.data()) : {}, data: Object.fromEntries(sourceEntries) };
}

async function readPriorDemandForecasts(businessId, activeRunId) {
  if (!activeRunId) return [];
  const states = await readCollection(businessId, 'agentState');
  return states
    .filter((row) => row.analysisRunId === activeRunId && row.capabilityId === 'D4' && row.outputType === 'DemandForecast' && row.payload)
    .map((row) => row.payload);
}

function stamp(value) {
  if (!value) return null;
  const d = parseDate(value);
  return d ? d.toISOString() : String(value);
}

function pythonCandidates() {
  return [
    process.env.PROCESSING_PYTHON,
    path.join(FOUNDATION, '.venv-florah-test', 'Scripts', 'python.exe'),
    path.join(FOUNDATION, '.venv-florah-test', 'bin', 'python'),
    'python'
  ].filter(Boolean);
}

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: FOUNDATION, windowsHide: true, shell: false });
    let out = '', err = '';
    child.stdout.on('data', (chunk) => { out += chunk.toString(); });
    child.stderr.on('data', (chunk) => { err += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => code === 0 ? resolve({ out, err }) : reject(new Error(`${command} exited with ${code}. ${err || out}`)));
  });
}

async function runDemandSource(payload) {
  if (!fs.existsSync(demandScript)) throw new Error('Demand processing bridge is missing.');
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'sme-demand-'));
  const input = path.join(folder, 'input.json');
  fs.writeFileSync(input, JSON.stringify(payload), 'utf8');
  let lastError = null;
  try {
    for (const candidate of pythonCandidates()) {
      if (candidate !== 'python' && !fs.existsSync(candidate)) continue;
      try {
        const { out } = await runCommand(candidate, [demandScript, '--input', input]);
        return JSON.parse(out.trim());
      } catch (error) { lastError = error; }
    }
    throw lastError || new Error('Python is unavailable for the Demand domain.');
  } finally {
    fs.rmSync(folder, { recursive: true, force: true });
  }
}

function demandResults(native) {
  const results = [], byProduct = new Map();
  for (const [productId, row] of Object.entries(native.products || {})) {
    const item = {};
    const d1 = row.D1;
    if (d1?.status === 'INSUFFICIENT_EVIDENCE') results.push(insufficient({ capabilityId:'D1',domain:'demand',outputType:'CleanDemandSeries',entityType:'product',entityId:productId,reason:d1.reason || 'Insufficient sales history.' }));
    else {
      item.D1 = d1;
      results.push(makeResult({ capabilityId:'D1',domain:'demand',outputType:'CleanDemandSeries',entityType:'product',entityId:productId,payload:d1,confidence:clamp(d1?.diagnostics?.coverage_pct ?? 0.7),riskLevel:'LOW',inputRefs:['transactions'] }));
    }
    const d2 = row.D2;
    if (!d2 || d2.status === 'INSUFFICIENT_EVIDENCE' || d2.status === 'SKIPPED') results.push(insufficient({ capabilityId:'D2',domain:'demand',outputType:'SeasonalityProfile',entityType:'product',entityId:productId,reason:d2?.reason || 'Seasonality could not be established.',inputRefs:['D1'] }));
    else {
      item.D2 = d2;
      results.push(makeResult({ capabilityId:'D2',domain:'demand',outputType:'SeasonalityProfile',entityType:'product',entityId:productId,payload:d2,confidence:Number(d2.confidence || 0.5),riskLevel:Number(d2.confidence || 0) < 0.5 ? 'MEDIUM':'LOW',inputRefs:['D1'] }));
    }
    const d3 = row.D3;
    if (!d3 || d3.status === 'INSUFFICIENT_EVIDENCE' || d3.status === 'SKIPPED') results.push(insufficient({ capabilityId:'D3',domain:'demand',outputType:'DemandSignalAdjustment',entityType:'product',entityId:productId,reason:d3?.reason || 'Demand signals could not be evaluated.',inputRefs:['D1','promotions','localEvents'] }));
    else {
      item.D3 = d3;
      const sigConf = Math.max(0.7, ...(d3.signals || []).map((s) => Number(s.confidence || 0)));
      results.push(makeResult({ capabilityId:'D3',domain:'demand',outputType:'DemandSignalAdjustment',entityType:'product',entityId:productId,payload:d3,confidence:clamp(sigConf),riskLevel:'LOW',inputRefs:['D1','promotions','localEvents'] }));
    }
    const d4 = row.D4;
    if (!d4) results.push(insufficient({ capabilityId:'D4',domain:'demand',outputType:'DemandForecast',entityType:'product',entityId:productId,reason:row.D4_error || 'A demand forecast could not be produced.',inputRefs:['D1','D2','D3'] }));
    else {
      item.D4 = d4;
      results.push(makeResult({ capabilityId:'D4',domain:'demand',outputType:'DemandForecast',entityType:'product',entityId:productId,payload:d4,confidence:Number(d4.confidence || 0),riskLevel:Number(d4.confidence || 0) < 0.5 ? 'MEDIUM':'LOW',status:d4.insufficient_evidence ? 'SKIPPED':'SUCCEEDED',inputRefs:['D1','D2','D3'],model:'florah-demand' }));
    }
    const d5 = row.D5;
    item.D5 = d5;
    const reportStatus = String(d5?.report?.status || d5?.status || '');
    const d5Skipped = /INSUFFICIENT|SKIPPED/i.test(reportStatus);
    const alertRisk = highestRisk((d5?.alerts || []).map((a) => a.severity), d5Skipped ? 'MEDIUM':'LOW');
    results.push(makeResult({ capabilityId:'D5',domain:'demand',outputType:'ForecastQualityAlert',entityType:'product',entityId:productId,payload:d5 || {status:'INSUFFICIENT_EVIDENCE'},confidence:d5Skipped?0.3:0.9,riskLevel:alertRisk,status:d5Skipped?'SKIPPED':'SUCCEEDED',inputRefs:['D4','transactions'],model:'florah-demand' }));
    byProduct.set(productId, item);
  }
  return { results, byProduct };
}

function grouped(rows, field) {
  const map = new Map();
  for (const row of rows || []) { const k=String(row[field] || ''); if(!map.has(k))map.set(k,[]); map.get(k).push(row); }
  return map;
}

function pricingResults({ products, competitorPrices, transactions, demandByProduct, inventoryByProduct, now }) {
  const comp = grouped(competitorPrices, 'product_id'), tx = grouped(transactions, 'product_id');
  const results = [], recommendations = [], byProduct = new Map();
  for (const product of (products || []).filter((p) => p.active !== false)) {
    const productId = String(product.product_id), d4 = demandByProduct.get(productId)?.D4, inv = inventoryByProduct.get(productId) || {};
    if (!d4) {
      for (const [cap, type] of [['P1','CompetitorPriceSignal'],['P2','AllowedPriceRange'],['P3','ElasticityEstimate'],['P4','PromoPriceCandidate'],['P5','PriceRecommendation']]) results.push(insufficient({ capabilityId:cap,domain:'pricing',outputType:type,entityType:'product',entityId:productId,reason:'Pricing waits for a usable demand forecast for this product.' }));
      continue;
    }
    const priceProduct = { product_id:productId,current_price:Number(product.sell_price || 0),unit_cost:Number(product.unit_cost || 0),variable_fees_per_unit:Number(product.variable_fees_per_unit || 0),margin_floor_pct:Number(product.margin_floor_pct ?? 0.20),currency:'ZAR' };
    const out = runPricingDomain({ product:priceProduct, competitorObservations:comp.get(productId)||[], transactions:tx.get(productId)||[], d4, i1:inv.I1, i4:inv.I4, policy:pricingPolicy, now });
    byProduct.set(productId, out);
    const defs = [
      ['P1','CompetitorPriceSignal',out.p1,out.p1.status==='OK'?'LOW':'MEDIUM',out.p1.status==='OK'?'SUCCEEDED':'SKIPPED'],
      ['P2','AllowedPriceRange',out.p2,out.p2.status==='OK'?'LOW':'HIGH',out.p2.status==='OK'?'SUCCEEDED':'SKIPPED'],
      ['P3','ElasticityEstimate',out.p3,out.p3.status==='ESTIMATED'?'LOW':'MEDIUM',out.p3.status==='ESTIMATED'?'SUCCEEDED':'SKIPPED'],
      ['P4','PromoPriceCandidate',out.p4,out.p4.actionable?'MEDIUM':'LOW','SUCCEEDED'],
      ['P5','PriceRecommendation',out.p5,out.p5.risk_level||'MEDIUM',out.p5.status==='DRAFT'?'SKIPPED':'SUCCEEDED']
    ];
    for (const [cap,type,payload,risk,status] of defs) results.push(makeResult({ capabilityId:cap,domain:'pricing',outputType:type,entityType:'product',entityId:productId,payload,confidence:Number(payload.confidence || (cap==='P2'?1:0.5)),riskLevel:risk,status,inputRefs:cap==='P5'?['P1','P2','P3','P4','D4','I1','I4']:[] }));
    if (out.p5.status === 'READY_FOR_REVIEW' && out.p5.actionable) recommendations.push({ capabilityId:'P5',domain:'pricing',recommendationType:'Price recommendation',subjectType:'product',subjectId:productId,action:{...out.p5,minimum_safe_price:out.p2.minimum_price,maximum_change_pct:pricingPolicy.maximumSinglePriceChangePct},confidence:Number(out.p5.confidence || 0.5),riskLevel:out.p5.risk_level || 'MEDIUM' });
  }
  return { results, recommendations, byProduct };
}

function ensureAllCapabilities(results) {
  const have = new Set(results.map((r) => r.capabilityId));
  for (const cap of normalizedCapabilities()) {
    if (have.has(cap.capabilityId)) continue;
    results.push(insufficient({ capabilityId:cap.capabilityId,domain:cap.domain,outputType:cap.primaryOutput,entityType:'business',entityId:'business',reason:'There are no source records available for this function yet.' }));
  }
}

function recommendationsFromProcurement(procurement) {
  const rows = [];
  for (const [productId, r4] of procurement.r4ByProduct.entries()) {
    if (r4.status === 'READY_FOR_REVIEW' && r4.actionable) rows.push({ capabilityId:'R4',domain:'procurement',recommendationType:'Purchase recommendation',subjectType:'product',subjectId:productId,action:r4,confidence:Number(r4.confidence || 0.5),riskLevel:r4.risk || 'MEDIUM' });
  }
  return rows;
}

function eventsFromResults(results, recommendations) {
  const events = [];
  const add=(eventType,sourceAgent,entityId,payload={})=>events.push({eventType,sourceAgent,entityId,payload});
  for (const r of results) {
    if (r.status !== 'SUCCEEDED') continue;
    if (r.capabilityId === 'D4') add('demand.forecast.updated.v1','D4',r.entityId,{expected_qty:r.payload.expected_qty,confidence:r.payload.confidence});
    if (r.capabilityId === 'I1') add('inventory.stock.updated.v1','I1',r.entityId,{stock_status:r.payload.stock_status,available_stock:r.payload.available_stock});
    if (r.capabilityId === 'R2') add('procurement.supplier-performance.updated.v1','R2',r.entityId,{score:r.payload.score});
    if (r.capabilityId === 'C1') add('customer.segment.updated.v1','C1',r.entityId,{segment:r.payload.segment});
    if (r.capabilityId === 'C2') add('customer.retention-risk.changed.v1','C2',r.entityId,{risk_band:r.payload.riskBand});
    if (r.capabilityId === 'C3' && r.payload.eligible) add('customer.promotion.recommended.v1','C3',r.entityId,{product_id:r.payload.productId,offer_pct:r.payload.offerPct});
    if (r.capabilityId === 'C5' && r.payload.sentiment !== 'neutral') add('customer.feedback-insight.created.v1','C5',r.entityId,{sentiment:r.payload.sentiment,urgency:r.payload.urgency});
  }
  for (const rec of recommendations) {
    if (rec.capabilityId === 'P5') add('pricing.recommendation.created.v1','P5',rec.subjectId,{risk_level:rec.riskLevel});
    if (rec.capabilityId === 'R4') add('procurement.recommendation.created.v1','R4',rec.subjectId,{risk_level:rec.riskLevel});
    if (rec.capabilityId === 'C4') add('customer.next-action.recommended.v1','C4',rec.subjectId,{priority:rec.action.priority});
  }
  return events;
}

async function commitChunks(ops, chunkSize = 350) {
  const db = services();
  for (let i=0;i<ops.length;i+=chunkSize) {
    const batch=db.batch();
    for (const op of ops.slice(i,i+chunkSize)) op(batch);
    await batch.commit();
  }
}

async function publish({ businessId, actor, runId, sourceStamp, results, recommendations, events, summary, startedAt }) {
  const db=services();
  const now=new Date();
  const ops=[];
  for (const result of results) {
    const stateId=`${result.capabilityId}:${stableId(result.outputType,result.entityId)}`;
    const outputId=`${runId}:${stableId(result.capabilityId,result.outputType,result.entityId)}`;
    const common={businessId,capabilityId:result.capabilityId,sourceAgent:result.capabilityId,domain:result.domain,outputType:result.outputType,entityType:result.entityType,entityId:result.entityId,payload:result.payload,inputRefs:result.inputRefs||[],confidence:Number(result.confidence||0),riskLevel:result.riskLevel||'LOW',generatedAt:now.toISOString(),modelOrRuleVersion:result.model||'integrated',runId,analysisRunId:runId,correlationId:runId,sourceDataUpdatedAt:sourceStamp};
    ops.push((batch)=>safeSet(batch,db.doc(`businesses/${businessId}/agentOutputs/${outputId}`),{...common,outputId,stateId}));
    ops.push((batch)=>safeSet(batch,db.doc(`businesses/${businessId}/agentState/${stateId}`),{...common,stateId,outputId},{merge:false}));
    const invocationId=`${runId}:${result.capabilityId}:${stableId(result.entityType,result.entityId)}`;
    ops.push((batch)=>safeSet(batch,db.doc(`businesses/${businessId}/agentRuns/${invocationId}`),{runId:invocationId,analysisRunId:runId,capabilityId:result.capabilityId,domain:result.domain,entityType:result.entityType,entityId:result.entityId,status:result.status,startedAt:startedAt.toISOString(),completedAt:now.toISOString(),durationMs:Math.max(1,now.getTime()-startedAt.getTime()),inputRefs:result.inputRefs||[],outputId,actorId:actor,error:result.status==='FAILED'?result.message||'Processing failed':null}));
  }
  for (const rec of recommendations) {
    const recommendationId=`${rec.capabilityId}-${stableId(rec.capabilityId,rec.subjectId)}`;
    ops.push((batch)=>safeSet(batch,db.doc(`businesses/${businessId}/agentRecommendations/${recommendationId}`),{recommendationId,analysisRunId:runId,runId,capabilityId:rec.capabilityId,domain:rec.domain,recommendationType:rec.recommendationType,subjectType:rec.subjectType,subjectId:String(rec.subjectId),action:rec.action,confidence:Number(rec.confidence||0),riskLevel:rec.riskLevel||'MEDIUM',status:'READY_FOR_REVIEW',createdAt:now.toISOString(),updatedAt:now.toISOString(),correlationId:runId},{merge:false}));
  }
  for (const event of events) {
    const eventId=randomUUID();
    ops.push((batch)=>safeSet(batch,db.doc(`businesses/${businessId}/agentEvents/${eventId}`),{eventId,analysisRunId:runId,eventType:event.eventType,sourceAgent:event.sourceAgent,status:'RECORDED',createdAt:now.toISOString(),payload:event.payload||{},entityId:String(event.entityId||'business'),correlationId:runId}));
  }
  await commitChunks(ops);
  const latestBusiness=await db.doc(`businesses/${businessId}`).get();
  if (stamp(clean(latestBusiness.data()?.dataUpdatedAt)) !== stamp(sourceStamp)) {
    const err=new Error('Business data changed while processing was running. No new results were activated. Run processing again.'); err.code='DATA_CHANGED_DURING_PROCESSING'; throw err;
  }
  const finalBatch=db.batch();
  finalBatch.set(db.doc(`businesses/${businessId}`),{analysisStatus:'CURRENT',activeAnalysisRunId:runId,lastProcessedAt:FieldValue.serverTimestamp(),processingRunId:FieldValue.delete(),processingStartedAt:FieldValue.delete(),processingSummary:summary},{merge:true});
  finalBatch.set(db.doc(`businesses/${businessId}/agentRuns/${runId}`),{status:'SUCCEEDED',completedAt:FieldValue.serverTimestamp(),durationMs:Date.now()-startedAt.getTime(),summary},{merge:true});
  await finalBatch.commit();
}

export async function getProcessingReadiness(businessId) {
  const snap=await readBusinessSnapshot(businessId); const d=snap.data; const b=snap.business;
  const count=(k)=>d[k]?.length||0;
  const domains=[
    {key:'demand',label:'Demand',status:count('products')&&count('transactions')?'READY':'NEEDS_DATA',detail:`${count('products')} products · ${count('transactions')} sales records`,issues:[!count('products')?'Add products.':null,!count('transactions')?'Add sales history.':null].filter(Boolean)},
    {key:'inventory',label:'Inventory',status:count('inventorySnapshots')?'READY':'NEEDS_DATA',detail:`${count('inventorySnapshots')} stock counts · ${count('inventoryMovements')} stock movements`,issues:[!count('inventorySnapshots')?'Add at least one stock count.':null].filter(Boolean)},
    {key:'procurement',label:'Procurement',status:count('suppliers')&&count('supplierQuotes')?'READY':'PARTIAL',detail:`${count('suppliers')} suppliers · ${count('supplierQuotes')} quotes · ${count('supplierPerformance')} performance records`,issues:[!count('suppliers')?'Add suppliers.':null,!count('supplierQuotes')?'Add supplier quotes for purchase recommendations.':null].filter(Boolean)},
    {key:'pricing',label:'Pricing',status:count('products')?'READY':'NEEDS_DATA',detail:`${count('competitorPrices')} competitor observations · ${count('transactions')} sales observations`,issues:[!count('competitorPrices')?'Competitor pricing will stay unavailable until observations are added.':null].filter(Boolean)},
    {key:'customer-engagement',label:'Customers',status:count('customers')?'READY':'PARTIAL',detail:`${count('customers')} customers · ${count('feedback')} feedback records`,issues:[!count('customers')?'Customer analysis will be skipped until customer records are added.':null].filter(Boolean)}
  ];
  return { canProcess:count('products')>0&&count('transactions')>0,analysisStatus:b.analysisStatus||'NEEDS_PROCESSING',dataUpdatedAt:stamp(b.dataUpdatedAt),lastProcessedAt:stamp(b.lastProcessedAt),activeAnalysisRunId:b.activeAnalysisRunId||null,processingRunId:b.processingRunId||null,domains,counts:Object.fromEntries(SOURCE_COLLECTIONS.map((k)=>[k,count(k)])) };
}

export async function processBusiness({businessId,actor}) {
  const db=services(); const startedAt=new Date(); const runId=`analysis-${startedAt.toISOString().replace(/[-:.TZ]/g,'')}-${randomUUID().slice(0,8)}`;
  const businessRef=db.doc(`businesses/${businessId}`);
  let sourceStamp=null;
  await db.runTransaction(async(tx)=>{
    const before=await tx.get(businessRef); const beforeData=clean(before.data()||{});
    if (beforeData.processingRunId) {
      const started = parseDate(beforeData.processingStartedAt);
      const stillFresh = started && (Date.now() - started.getTime()) < PROCESSING_LEASE_MS;
      if (stillFresh) { const err=new Error('A processing run is already active for this business.'); err.code='PROCESSING_ALREADY_RUNNING'; throw err; }
    }
    sourceStamp=stamp(beforeData.dataUpdatedAt);
    tx.set(businessRef,{analysisStatus:'PROCESSING',processingRunId:runId,processingStartedAt:startedAt.toISOString(),lastProcessingError:FieldValue.delete()},{merge:true});
  });
  await db.doc(`businesses/${businessId}/agentRuns/${runId}`).set(firestoreSafe({runId,analysisRunId:runId,capabilityId:'PROCESS',domain:'platform',entityType:'business',entityId:businessId,status:'RUNNING',startedAt:startedAt.toISOString(),actorId:actor}));
  try {
    const snapshot=await readBusinessSnapshot(businessId); const d=snapshot.data;
    if (!d.products.length || !d.transactions.length) { const err=new Error('Add products and sales history before processing.'); err.code='PROCESSING_NOT_READY'; throw err; }
    const priorForecasts=await readPriorDemandForecasts(businessId, snapshot.business.activeAnalysisRunId || null);
    const demandNative=await runDemandSource({products:d.products,transactions:d.transactions,promotions:d.promotions,localEvents:d.localEvents,priorForecasts});
    const demand=demandResults(demandNative);
    const evidence=buildSupplierEvidence({suppliers:d.suppliers,supplierQuotes:d.supplierQuotes,supplierPerformance:d.supplierPerformance,now:startedAt});
    const inventory=runInventoryDomain({products:d.products,inventorySnapshots:d.inventorySnapshots,inventoryMovements:d.inventoryMovements,transactions:d.transactions,purchaseOrders:d.purchaseOrders,goodsReceipts:d.goodsReceipts,demandByProduct:demand.byProduct,supplierContextByProduct:evidence.supplierContextByProduct,now:startedAt});
    const procurement=runProcurementDomain({products:d.products,suppliers:d.suppliers,supplierQuotes:d.supplierQuotes,supplierPerformance:d.supplierPerformance,purchaseOrders:d.purchaseOrders,goodsReceipts:d.goodsReceipts,invoices:d.invoices,demandByProduct:demand.byProduct,inventoryByProduct:inventory.byProduct,evidence,now:startedAt});
    const pricing=pricingResults({products:d.products,competitorPrices:d.competitorPrices,transactions:d.transactions,demandByProduct:demand.byProduct,inventoryByProduct:inventory.byProduct,now:startedAt});
    const customer=await runCustomerDomain({businessId,customers:d.customers,transactions:d.transactions,products:d.products,feedback:d.feedback,inventoryByProduct:inventory.byProduct,now:startedAt});
    const results=[...demand.results,...inventory.results,...procurement.results,...pricing.results,...customer.results]; ensureAllCapabilities(results);
    const recommendations=[...recommendationsFromProcurement(procurement),...pricing.recommendations,...customer.recommendations];
    const events=eventsFromResults(results,recommendations);
    const summary={capabilities:25,results:results.length,recommendations:recommendations.length,events:events.length,products:d.products.length,customers:d.customers.length,completedDomains:5,skippedResults:results.filter((r)=>r.status==='SKIPPED').length};
    await publish({businessId,actor,runId,sourceStamp,results,recommendations,events,summary,startedAt});
    return {ok:true,runId,summary};
  } catch(error) {
    const dataChanged = error?.code === 'DATA_CHANGED_DURING_PROCESSING';
    await db.doc(`businesses/${businessId}`).set({analysisStatus:dataChanged?'NEEDS_PROCESSING':'FAILED',processingRunId:FieldValue.delete(),processingStartedAt:FieldValue.delete(),lastProcessingError:String(error.message||error)},{merge:true}).catch(()=>{});
    await db.doc(`businesses/${businessId}/agentRuns/${runId}`).set(firestoreSafe({status:'FAILED',completedAt:FieldValue.serverTimestamp(),durationMs:Date.now()-startedAt.getTime(),error:String(error.message||error)}),{merge:true}).catch(()=>{});
    throw error;
  }
}
