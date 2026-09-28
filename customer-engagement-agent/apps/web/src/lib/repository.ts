import { demoData, id, runBusinessCycle, type AgentEvent, type Feedback, type Insight, type SyncQueueItem } from '@cea/shared';
import { db } from './db';
import { eventBus } from './eventBus';

function queueRecord(businessId: string, collection: SyncQueueItem['collection'], docId: string, payload: Record<string, unknown>): SyncQueueItem {
  const now = new Date().toISOString();
  return { id: id('sync'), businessId, collection, docId, operation: 'upsert', payload, status: 'pending', attempts: 0, createdAt: now, updatedAt: now };
}

export async function seedDemoData() {
  const seeded = await db.meta.get('demo-seeded');
  if (seeded) return;
  const data = demoData();
  await db.transaction('rw', [db.customers, db.transactions, db.products, db.feedback, db.meta], async () => {
    await db.customers.bulkPut(data.customers);
    await db.transactions.bulkPut(data.transactions);
    await db.products.bulkPut(data.products);
    await db.feedback.bulkPut(data.feedback);
    await db.meta.put({ key: 'demo-seeded', value: new Date().toISOString() });
  });
}

export async function resetDemoData() {
  await db.transaction('rw', [db.customers, db.transactions, db.products, db.feedback, db.insights, db.events, db.syncQueue, db.syncAudit, db.meta], async () => {
    await Promise.all([db.customers.clear(), db.transactions.clear(), db.products.clear(), db.feedback.clear(), db.insights.clear(), db.events.clear(), db.syncQueue.clear(), db.syncAudit.clear(), db.meta.clear()]);
  });
  await seedDemoData();
}

export async function addFeedback(input: Omit<Feedback, 'id' | 'createdAt' | 'status'>) {
  const feedback: Feedback = { ...input, id: id('fb'), createdAt: new Date().toISOString(), status: 'new' };
  const queue = queueRecord(input.businessId, 'feedback', feedback.id, feedback as unknown as Record<string, unknown>);
  await db.transaction('rw', [db.feedback, db.syncQueue], async () => {
    await db.feedback.put(feedback);
    await db.syncQueue.put(queue);
  });
  return feedback;
}

const eventTargets: Record<string, AgentEvent['targetAgents']> = {
  C1: ['Sales', 'Coordinator'], C2: ['Sales', 'Coordinator'], C3: ['Inventory', 'Pricing', 'Coordinator'], C4: ['Coordinator'], C5: ['Sales', 'Coordinator']
};

export async function runAndPersistBusinessCycle(businessId: string) {
  const [customers, transactions, products, feedback] = await Promise.all([
    db.customers.where('businessId').equals(businessId).toArray(),
    db.transactions.where('businessId').equals(businessId).toArray(),
    db.products.where('businessId').equals(businessId).toArray(),
    db.feedback.where('businessId').equals(businessId).toArray()
  ]);
  const now = new Date().toISOString();
  const results = runBusinessCycle(customers, transactions, products, feedback, now);
  const insights: Insight[] = [];
  const events: AgentEvent[] = [];

  for (const result of results) {
    const pieces = [result.segment, result.churn, result.promotion, result.nextAction, result.feedback];
    for (const piece of pieces) {
      const explanation = 'reasons' in piece ? piece.reasons : [];
      const score = piece.agentId === 'C1' ? piece.score : piece.agentId === 'C2' ? piece.riskScore : piece.agentId === 'C3' ? piece.score : piece.agentId === 'C5' ? piece.sentimentScore : piece.priority === 'high' ? 90 : piece.priority === 'medium' ? 60 : 30;
      const insight: Insight = {
        id: `ins-${result.customerId}-${piece.agentId}`,
        businessId, customerId: result.customerId, agentId: piece.agentId,
        type: piece.agentId === 'C1' ? 'segment' : piece.agentId === 'C2' ? 'retention-risk' : piece.agentId === 'C3' ? 'promotion' : piece.agentId === 'C4' ? 'next-best-action' : 'feedback-sentiment',
        score, payload: piece as unknown as Record<string, unknown>, explanation, createdAt: now
      };
      insights.push(insight);
      const event: AgentEvent = {
        id: id('evt'), businessId,
        name: piece.agentId === 'C1' ? 'customer.segment.updated' : piece.agentId === 'C2' ? 'customer.retention.risk.changed' : piece.agentId === 'C3' ? 'customer.promotion.recommended' : piece.agentId === 'C4' ? 'customer.next_action.recommended' : 'customer.feedback.insight.created',
        producer: 'CustomerEngagement', targetAgents: eventTargets[piece.agentId], entityId: result.customerId,
        payload: piece as unknown as Record<string, unknown>, status: 'queued', createdAt: now
      };
      events.push(event);
    }
  }

  const queues = [
    ...insights.map(item => queueRecord(businessId, 'insights', item.id, item as unknown as Record<string, unknown>)),
    ...events.map(item => queueRecord(businessId, 'events', item.id, item as unknown as Record<string, unknown>))
  ];
  await db.transaction('rw', [db.insights, db.events, db.syncQueue], async () => {
    await db.insights.bulkPut(insights);
    await db.events.bulkPut(events);
    await db.syncQueue.bulkPut(queues);
  });
  events.forEach(event => eventBus.publish(event));
  return results;
}
