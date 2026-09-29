import { randomUUID } from 'node:crypto';
import { FieldValue } from 'firebase-admin/firestore';
import { getFirebaseServices } from '../firebase.mjs';
import { stableId } from './common.mjs';

function db() {
  const state=getFirebaseServices();
  if(!state.db) throw new Error(state.error?.message || 'Firestore is unavailable.');
  return state.db;
}

function asDateAfterDays(days) {
  const d=new Date(Date.now()+Math.max(1,Number(days)||1)*86_400_000);
  return d.toISOString().slice(0,10);
}

export async function executeApprovedRecommendation({businessId,recommendation,approvedAction,reviewer,decision}) {
  const store=db();
  const capability=String(recommendation.capabilityId||'');
  const recommendationId=String(recommendation.recommendationId||recommendation.id||'');
  const now=new Date().toISOString();
  const actionId=`action-${stableId(recommendationId,now)}`;
  const actionRef=store.doc(`businesses/${businessId}/agentActions/${actionId}`);
  const recRef=store.doc(`businesses/${businessId}/agentRecommendations/${recommendationId}`);
  const eventRef=store.doc(`businesses/${businessId}/agentEvents/${randomUUID()}`);
  const auditRef=store.doc(`businesses/${businessId}/auditLogs/${randomUUID()}`);
  const batch=store.batch();
  let sourceDataChanged=false;
  let executedTarget=null;

  if(capability==='P5') {
    const productId=String(recommendation.subjectId||approvedAction.product_id||'');
    const proposed=Number(approvedAction.proposed_price);
    if(!productId||!(proposed>0)) throw new Error('Approved price action is missing a valid product and price.');
    const current=Number(recommendation.action?.current_price||approvedAction.current_price||0);
    const minimum=Number(recommendation.action?.minimum_safe_price||approvedAction.minimum_safe_price||0);
    const maxChange=Number(recommendation.action?.maximum_change_pct||approvedAction.maximum_change_pct||0.15);
    if(minimum>0 && proposed<minimum-0.005) throw new Error(`The approved price cannot go below the safe margin floor of R${minimum.toFixed(2)}.`);
    if(current>0 && Math.abs((proposed-current)/current)>maxChange+0.0001) throw new Error(`The approved price change exceeds the ${(maxChange*100).toFixed(0)}% single-change limit.`);
    if(current>0 && proposed>current+0.005) throw new Error('This recommendation is a governed markdown. Increasing the price requires a new analysis rather than modifying this approval.');
    const productRef=store.doc(`businesses/${businessId}/products/${productId}`);
    const productSnap=await productRef.get();
    if(!productSnap.exists) throw new Error(`Product ${productId} no longer exists.`);
    const previous=productSnap.data()||{};
    batch.set(productRef,{...previous,sell_price:proposed,_meta:{...(previous._meta||{}),updatedAt:now,updatedBy:reviewer,source:(previous._meta||{}).source||'manual',lastApprovedPricingAction:recommendationId}},{merge:false});
    sourceDataChanged=true;
    executedTarget={type:'product_price',id:productId,price:proposed};
  } else if(capability==='R4') {
    const productId=String(approvedAction.product_id||recommendation.subjectId||'');
    const supplierId=String(approvedAction.supplier_id||'');
    const qty=Number(approvedAction.qty), unitCost=Number(approvedAction.unit_cost);
    if(!productId||!supplierId||!(qty>0)||!(unitCost>0)) throw new Error('Approved purchase action is missing product, supplier, quantity or unit cost.');
    const [productSnap,supplierSnap]=await Promise.all([
      store.doc(`businesses/${businessId}/products/${productId}`).get(),
      store.doc(`businesses/${businessId}/suppliers/${supplierId}`).get()
    ]);
    if(!productSnap.exists) throw new Error(`Product ${productId} no longer exists.`);
    if(!supplierSnap.exists) throw new Error(`Supplier ${supplierId} no longer exists.`);
    const poId=`PO-${stableId(recommendationId).toUpperCase()}`;
    const poRef=store.doc(`businesses/${businessId}/purchaseOrders/${poId}`);
    batch.set(poRef,{po_id:poId,recommendation_id:recommendationId,supplier_id:supplierId,product_id:productId,qty,unit_cost:unitCost,currency:approvedAction.currency||'ZAR',ordered_at:now,promised_date:asDateAfterDays(approvedAction.eta_days),status:'OPEN',created_by:reviewer,_meta:{source:'approved recommendation',createdAt:now,createdBy:reviewer,updatedAt:now,updatedBy:reviewer}},{merge:false});
    sourceDataChanged=true;
    executedTarget={type:'purchase_order',id:poId};
  } else {
    executedTarget={type:'work_item',id:actionId};
  }

  const actionStatus = ['P5','R4'].includes(capability) ? 'EXECUTED' : 'READY';
  const recommendationStatus = ['P5','R4'].includes(capability) ? 'EXECUTED' : 'APPROVED';
  batch.set(actionRef,{actionId,businessId,recommendationId,capabilityId:capability,domain:recommendation.domain||null,subjectId:recommendation.subjectId||null,action:approvedAction,status:actionStatus,createdAt:now,createdBy:reviewer,decision,executedTarget},{merge:false});
  batch.set(eventRef,{eventId:eventRef.id,eventType:'governance.recommendation.approved.v1',sourceAgent:'platform-governance',status:'RECORDED',createdAt:now,payload:{recommendationId,capabilityId:capability,decision,executedTarget},entityId:String(recommendation.subjectId||recommendationId),correlationId:recommendation.correlationId||recommendation.runId||recommendationId});
  batch.set(auditRef,{auditId:auditRef.id,eventType:'RECOMMENDATION_EXECUTED',actorId:reviewer,payload:{recommendationId,capabilityId:capability,decision,executedTarget},createdAt:FieldValue.serverTimestamp()});
  batch.set(recRef,{status:recommendationStatus,decisionStatus:decision,executionStatus:actionStatus,executedAt:actionStatus==='EXECUTED'?now:null,executedTarget,updatedAt:now},{merge:true});
  if(sourceDataChanged) batch.set(store.doc(`businesses/${businessId}`),{analysisStatus:'NEEDS_PROCESSING',dataUpdatedAt:FieldValue.serverTimestamp()},{merge:true});
  await batch.commit();
  return {actionId,executedTarget,sourceDataChanged,actionStatus,recommendationStatus};
}
