import { randomUUID } from 'node:crypto';
import { Timestamp } from 'firebase-admin/firestore';
import { getFirebaseServices } from './firebase.mjs';
import { normalizedCapabilities, backendStatus, demandStatus } from './architecture.mjs';
import { executeApprovedRecommendation } from './process/approval-executor.mjs';

function iso(value) {
  if (!value) return null;
  if (value instanceof Timestamp) return value.toDate().toISOString();
  if (typeof value.toDate === 'function') return value.toDate().toISOString();
  if (value instanceof Date) return value.toISOString();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toISOString();
}
function clean(value) {
  if (Array.isArray(value)) return value.map(clean);
  if (value && typeof value === 'object') {
    if (value instanceof Timestamp || typeof value.toDate === 'function') return iso(value);
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, clean(v)]));
  }
  return value;
}
function base(businessId, collection) {
  const { db, error } = getFirebaseServices();
  if (!db) { const err = new Error(error?.message || 'Firestore is unavailable.'); err.code = 'FIREBASE_UNAVAILABLE'; throw err; }
  return db.collection(`businesses/${businessId}/${collection}`);
}
async function list(collectionRef, orderField, limitCount = 100) {
  let query = collectionRef;
  if (orderField) query = query.orderBy(orderField, 'desc');
  const snap = await query.limit(limitCount).get();
  return snap.docs.map((doc) => ({ id: doc.id, ...clean(doc.data()) }));
}

export async function loadWorkspace(businessId) {
  const capabilities = normalizedCapabilities();
  const disconnected = !getFirebaseServices().db;
  if (disconnected) {
    return { connected:false,business:{id:businessId,name:'Business workspace'},capabilities,backendStatus,demandStatus,recommendations:[],events:[],runs:[],state:[],outcomes:[],analysis:{status:'CONNECTION_UNAVAILABLE',dataUpdatedAt:null,lastProcessedAt:null,activeRunId:null},summary:{reviewCount:0,runningCount:0,failedCount:0,recentEventCount:0} };
  }
  const { db } = getFirebaseServices();
  const businessSnap = await db.doc(`businesses/${businessId}`).get();
  const businessData = businessSnap.exists ? clean(businessSnap.data()) : {};
  const activeRunId = businessData.activeAnalysisRunId || null;
  const [allRecommendations, events, allRuns, allState, outcomes] = await Promise.all([
    list(base(businessId,'agentRecommendations'),'updatedAt',250),
    list(base(businessId,'agentEvents'),'createdAt',150),
    list(base(businessId,'agentRuns'),'startedAt',500),
    list(base(businessId,'agentState'),null,1000),
    list(base(businessId,'outcomes'),'recordedAt',100)
  ]);
  const recommendations = activeRunId ? allRecommendations.filter((x)=>x.analysisRunId===activeRunId) : allRecommendations.filter((x)=>!x.analysisRunId);
  const state = activeRunId ? allState.filter((x)=>x.analysisRunId===activeRunId) : allState.filter((x)=>!x.analysisRunId);
  const visibleEvents = activeRunId ? events.filter((x)=>!x.analysisRunId || x.analysisRunId===activeRunId) : events.filter((x)=>!x.analysisRunId);
  const runsForStatus = activeRunId ? allRuns.filter((x)=>x.analysisRunId===activeRunId && x.capabilityId!=='PROCESS') : allRuns.filter((x)=>x.capabilityId!=='PROCESS');
  const latestRun = new Map();
  for (const run of runsForStatus) if (!latestRun.has(run.capabilityId)) latestRun.set(run.capabilityId, run);
  const hydratedCapabilities = capabilities.map((cap)=>{ const run=latestRun.get(cap.capabilityId); return {...cap,liveStatus:run?.status||'IDLE',lastRunAt:run?.startedAt||null,lastRunId:run?.runId||null}; });
  return {
    connected:true,
    business:businessSnap.exists?{id:businessId,...businessData}:{id:businessId,name:businessId},
    capabilities:hydratedCapabilities,backendStatus,demandStatus,recommendations,events:visibleEvents,runs:allRuns,state,outcomes,
    analysis:{status:businessData.analysisStatus||'NEEDS_PROCESSING',dataUpdatedAt:businessData.dataUpdatedAt||null,lastProcessedAt:businessData.lastProcessedAt||null,activeRunId,processingRunId:businessData.processingRunId||null,lastError:businessData.lastProcessingError||null},
    summary:{reviewCount:recommendations.filter((x)=>['READY_FOR_REVIEW','READY_FOR_SECOND_REVIEW'].includes(x.status)).length,runningCount:allRuns.filter((x)=>x.status==='RUNNING').length,failedCount:allRuns.filter((x)=>x.status==='FAILED').length,recentEventCount:visibleEvents.length}
  };
}

export async function recordRecommendationDecision({businessId,recommendationId,reviewer,decision,reason=null,modifiedAction=null}) {
  if (!['APPROVED','MODIFIED','REJECTED'].includes(decision)) throw new Error('Decision must be APPROVED, MODIFIED or REJECTED.');
  if (decision==='MODIFIED' && (!modifiedAction || typeof modifiedAction!=='object')) throw new Error('A modified action is required when decision is MODIFIED.');
  const { db, error } = getFirebaseServices();
  if (!db) throw new Error(error?.message || 'Firestore is unavailable.');
  const recommendationRef=db.doc(`businesses/${businessId}/agentRecommendations/${recommendationId}`);
  const approvalId=randomUUID(); const approvalRef=db.doc(`businesses/${businessId}/approvalLog/${approvalId}`);
  let recommendation=null, approvedAction=null, reviewStage='PRIMARY', needsSecondReview=false, terminalStatus=decision;

  await db.runTransaction(async(tx)=>{
    const snap=await tx.get(recommendationRef); if(!snap.exists) throw new Error('Recommendation not found.');
    const rec={id:snap.id,...clean(snap.data())}; recommendation=rec;
    const isSecond=rec.status==='READY_FOR_SECOND_REVIEW';
    if(!['READY_FOR_REVIEW','READY_FOR_SECOND_REVIEW'].includes(rec.status)) throw new Error(`This recommendation is no longer waiting for a decision.`);
    if(isSecond && rec.firstReviewedBy===reviewer) throw new Error('A second review must be completed by a different authorised user.');
    if(isSecond && decision==='MODIFIED') throw new Error('The second reviewer can approve or reject the already reviewed action. Return it for a new recommendation if changes are needed.');

    reviewStage=isSecond?'SECONDARY':'PRIMARY';
    approvedAction=isSecond ? (rec.approvedAction || rec.action) : (decision==='MODIFIED'?modifiedAction:rec.action);
    const expectedCost=Number(approvedAction?.expected_cost || (Number(approvedAction?.qty||0)*Number(approvedAction?.unit_cost||0)) || 0);
    needsSecondReview=!isSecond && rec.capabilityId==='R4' && (expectedCost>=25000 || String(rec.riskLevel||approvedAction?.risk||'').toUpperCase()==='HIGH');
    if(decision==='REJECTED') terminalStatus='REJECTED';
    else if(needsSecondReview) terminalStatus='READY_FOR_SECOND_REVIEW';
    else terminalStatus=decision;

    const now=new Date().toISOString();
    tx.create(approvalRef,{approvalId,businessId,recommendationId,reviewer,decision,reviewStage,modifiedAction:decision==='MODIFIED'?modifiedAction:null,reason:reason||null,decidedAt:now,correlationId:rec.correlationId||randomUUID()});
    const update={status:terminalStatus,updatedAt:now,approvedAction,decisionReason:reason||null,executionStatus:terminalStatus==='REJECTED'?'NOT_APPLICABLE':terminalStatus==='READY_FOR_SECOND_REVIEW'?'AWAITING_SECOND_REVIEW':'PENDING'};
    if(needsSecondReview){update.firstReviewedBy=reviewer;update.firstReviewedAt=now;update.firstDecision=decision;}
    if(isSecond){update.secondReviewedBy=reviewer;update.secondReviewedAt=now;update.secondDecision=decision;}
    tx.update(recommendationRef,update);
  });

  if(terminalStatus==='REJECTED') return {ok:true,approvalId,recommendationId,status:'REJECTED',reviewStage};
  if(terminalStatus==='READY_FOR_SECOND_REVIEW') return {ok:true,approvalId,recommendationId,status:'READY_FOR_SECOND_REVIEW',reviewStage};
  try {
    const execution=await executeApprovedRecommendation({businessId,recommendation,approvedAction,reviewer,decision});
    return {ok:true,approvalId,recommendationId,status:execution.recommendationStatus||'APPROVED',reviewStage,execution};
  } catch(executionError) {
    await recommendationRef.set({executionStatus:'FAILED',executionError:String(executionError.message||executionError),updatedAt:new Date().toISOString()},{merge:true});
    throw new Error(`The decision was recorded, but the approved action could not be applied: ${executionError.message||executionError}`);
  }
}
