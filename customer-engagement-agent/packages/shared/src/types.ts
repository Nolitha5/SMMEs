export type AgentId = 'C1' | 'C2' | 'C3' | 'C4' | 'C5';
export type KnownPlatformAgent = 'CustomerEngagement' | 'Sales' | 'Inventory' | 'Pricing' | 'Finance' | 'Coordinator';
// Extensible so the final 25-agent platform can add agent IDs without changing this package first.
export type PlatformAgent = KnownPlatformAgent | (string & {});
export type CustomerSegment = 'champion' | 'loyal' | 'regular' | 'new' | 'at-risk' | 'dormant' | 'value-seeker';
export type Sentiment = 'positive' | 'neutral' | 'negative';
export type RiskBand = 'low' | 'medium' | 'high' | 'critical';

export interface Customer {
  id: string;
  businessId: string;
  name: string;
  phone?: string;
  consentMarketing: boolean;
  tags: string[];
  createdAt: string;
  lastVisitAt?: string;
}

export interface TransactionLine {
  productId: string;
  quantity: number;
  unitPrice: number;
}

export interface Transaction {
  id: string;
  businessId: string;
  customerId: string;
  total: number;
  items: TransactionLine[];
  createdAt: string;
  sourceAgent: 'Sales';
}

export interface Product {
  id: string;
  businessId: string;
  name: string;
  sku: string;
  category: string;
  stock: number;
  reorderLevel: number;
  marginPct: number;
  price: number;
  isActive: boolean;
  sourceAgent: 'Inventory' | 'Pricing';
}

export interface Feedback {
  id: string;
  businessId: string;
  customerId: string;
  channel: 'in-store' | 'whatsapp' | 'sms' | 'web' | 'other';
  message: string;
  createdAt: string;
  status: 'new' | 'reviewed' | 'resolved';
}

export interface SegmentResult {
  agentId: 'C1';
  customerId: string;
  segment: CustomerSegment;
  score: number;
  reasons: string[];
  metrics: { recencyDays: number; frequency90d: number; spend90d: number };
}

export interface FeedbackResult {
  agentId: 'C5';
  customerId: string;
  sentiment: Sentiment;
  sentimentScore: number;
  topics: string[];
  urgency: 'normal' | 'priority';
  reasons: string[];
}

export interface ChurnResult {
  agentId: 'C2';
  customerId: string;
  riskScore: number;
  riskBand: RiskBand;
  reasons: string[];
}

export interface PromotionResult {
  agentId: 'C3';
  customerId: string;
  eligible: boolean;
  productId?: string;
  productName?: string;
  offerPct?: number;
  score: number;
  reasons: string[];
}

export interface NextActionResult {
  agentId: 'C4';
  customerId: string;
  action: 'service-recovery' | 'retention-offer' | 'promotion' | 'loyalty-thanks' | 'feedback-request' | 'no-action';
  priority: 'low' | 'medium' | 'high';
  channel: 'in-store' | 'whatsapp' | 'sms' | 'none';
  summary: string;
  reasons: string[];
}

export interface CustomerCycleResult {
  customerId: string;
  segment: SegmentResult;
  feedback: FeedbackResult;
  churn: ChurnResult;
  promotion: PromotionResult;
  nextAction: NextActionResult;
}

export interface Insight {
  id: string;
  businessId: string;
  customerId: string;
  agentId: AgentId;
  type: string;
  score: number;
  payload: Record<string, unknown>;
  explanation: string[];
  createdAt: string;
}

export interface AgentEvent {
  id: string;
  businessId: string;
  name: string;
  producer: PlatformAgent;
  targetAgents: PlatformAgent[];
  entityId: string;
  payload: Record<string, unknown>;
  status: 'local' | 'queued' | 'synced';
  createdAt: string;
}

export interface SyncQueueItem {
  id: string;
  businessId: string;
  collection: 'customers' | 'transactions' | 'products' | 'feedback' | 'insights' | 'events' | 'syncAudit';
  docId: string;
  operation: 'upsert' | 'delete';
  payload: Record<string, unknown>;
  status: 'pending' | 'syncing' | 'failed';
  attempts: number;
  createdAt: string;
  updatedAt: string;
  lastError?: string;
}
