import type { AgentEvent, Customer, CustomerCycleResult, Feedback, Insight, Product, Transaction } from '../types.js';
import { id } from '../utils.js';
import { runBusinessCycle } from '../agents/coordinator.js';
import { CUSTOMER_ENGAGEMENT_CONTRACT_VERSION, CUSTOMER_ENGAGEMENT_EVENT_TYPES } from './manifest.js';

export interface CustomerEngagementDataPort {
  readCustomers(businessId: string): Promise<Customer[]>;
  readTransactions(businessId: string): Promise<Transaction[]>;
  readProducts(businessId: string): Promise<Product[]>;
  readFeedback(businessId: string): Promise<Feedback[]>;
  writeInsights(businessId: string, insights: Insight[]): Promise<void>;
  publishEvents(businessId: string, events: AgentEvent[]): Promise<void>;
}

export interface CustomerEngagementExecutionResult {
  agentId: 'customer-engagement';
  contractVersion: typeof CUSTOMER_ENGAGEMENT_CONTRACT_VERSION;
  businessId: string;
  generatedAt: string;
  customerCount: number;
  results: CustomerCycleResult[];
  insights: Insight[];
  events: AgentEvent[];
}

const eventTargets: Record<'C1' | 'C2' | 'C3' | 'C4' | 'C5', AgentEvent['targetAgents']> = {
  C1: ['Sales', 'Coordinator'],
  C2: ['Sales', 'Coordinator'],
  C3: ['Inventory', 'Pricing', 'Coordinator'],
  C4: ['Coordinator'],
  C5: ['Sales', 'Coordinator']
};

function assertBusinessScope<T extends { businessId: string }>(businessId: string, rows: T[], label: string) {
  const mismatched = rows.find(row => row.businessId !== businessId);
  if (mismatched) throw new Error(`${label} contains data for another business (${mismatched.businessId}).`);
}

export function materializeCustomerEngagementArtifacts(
  businessId: string,
  results: CustomerCycleResult[],
  createdAt = new Date().toISOString()
): { insights: Insight[]; events: AgentEvent[] } {
  const insights: Insight[] = [];
  const events: AgentEvent[] = [];

  for (const result of results) {
    const pieces = [result.segment, result.churn, result.promotion, result.nextAction, result.feedback] as const;
    for (const piece of pieces) {
      const explanation = 'reasons' in piece ? piece.reasons : [];
      const score = piece.agentId === 'C1'
        ? piece.score
        : piece.agentId === 'C2'
          ? piece.riskScore
          : piece.agentId === 'C3'
            ? piece.score
            : piece.agentId === 'C5'
              ? piece.sentimentScore
              : piece.priority === 'high' ? 90 : piece.priority === 'medium' ? 60 : 30;

      const type = piece.agentId === 'C1'
        ? 'segment'
        : piece.agentId === 'C2'
          ? 'retention-risk'
          : piece.agentId === 'C3'
            ? 'promotion'
            : piece.agentId === 'C4'
              ? 'next-best-action'
              : 'feedback-sentiment';

      const eventName = piece.agentId === 'C1'
        ? CUSTOMER_ENGAGEMENT_EVENT_TYPES.segmentUpdated
        : piece.agentId === 'C2'
          ? CUSTOMER_ENGAGEMENT_EVENT_TYPES.retentionRiskChanged
          : piece.agentId === 'C3'
            ? CUSTOMER_ENGAGEMENT_EVENT_TYPES.promotionRecommended
            : piece.agentId === 'C4'
              ? CUSTOMER_ENGAGEMENT_EVENT_TYPES.nextActionRecommended
              : CUSTOMER_ENGAGEMENT_EVENT_TYPES.feedbackInsightCreated;

      insights.push({
        id: `ins-${result.customerId}-${piece.agentId}`,
        businessId,
        customerId: result.customerId,
        agentId: piece.agentId,
        type,
        score,
        payload: piece as unknown as Record<string, unknown>,
        explanation,
        createdAt
      });

      events.push({
        id: id('evt'),
        businessId,
        name: eventName,
        producer: 'CustomerEngagement',
        targetAgents: eventTargets[piece.agentId],
        entityId: result.customerId,
        payload: {
          contractVersion: CUSTOMER_ENGAGEMENT_CONTRACT_VERSION,
          ...piece as unknown as Record<string, unknown>
        },
        status: 'queued',
        createdAt
      });
    }
  }

  return { insights, events };
}

export async function executeCustomerEngagementCycle(
  port: CustomerEngagementDataPort,
  businessId: string,
  nowIso = new Date().toISOString()
): Promise<CustomerEngagementExecutionResult> {
  if (!businessId.trim()) throw new Error('businessId is required.');

  const [customers, transactions, products, feedback] = await Promise.all([
    port.readCustomers(businessId),
    port.readTransactions(businessId),
    port.readProducts(businessId),
    port.readFeedback(businessId)
  ]);

  assertBusinessScope(businessId, customers, 'customers');
  assertBusinessScope(businessId, transactions, 'transactions');
  assertBusinessScope(businessId, products, 'products');
  assertBusinessScope(businessId, feedback, 'feedback');

  const results = runBusinessCycle(customers, transactions, products, feedback, nowIso);
  const { insights, events } = materializeCustomerEngagementArtifacts(businessId, results, nowIso);

  await port.writeInsights(businessId, insights);
  await port.publishEvents(businessId, events);

  return {
    agentId: 'customer-engagement',
    contractVersion: CUSTOMER_ENGAGEMENT_CONTRACT_VERSION,
    businessId,
    generatedAt: nowIso,
    customerCount: customers.length,
    results,
    insights,
    events
  };
}
