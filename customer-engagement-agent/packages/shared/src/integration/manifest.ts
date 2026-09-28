export const CUSTOMER_ENGAGEMENT_AGENT_ID = 'customer-engagement' as const;
export const CUSTOMER_ENGAGEMENT_CONTRACT_VERSION = '1.0.0' as const;

export const CUSTOMER_ENGAGEMENT_EVENT_TYPES = {
  segmentUpdated: 'customer.segment.updated',
  retentionRiskChanged: 'customer.retention.risk.changed',
  promotionRecommended: 'customer.promotion.recommended',
  feedbackInsightCreated: 'customer.feedback.insight.created',
  nextActionRecommended: 'customer.next_action.recommended'
} as const;

export const CUSTOMER_ENGAGEMENT_INPUT_EVENTS = [
  'sales.transaction.recorded',
  'inventory.stock.changed',
  'pricing.product.changed',
  'customer.profile.changed',
  'customer.feedback.created'
] as const;

export const CUSTOMER_ENGAGEMENT_MANIFEST = {
  agentId: CUSTOMER_ENGAGEMENT_AGENT_ID,
  displayName: 'Customer Engagement Agent',
  contractVersion: CUSTOMER_ENGAGEMENT_CONTRACT_VERSION,
  architecture: 'one-agent-five-internal-capabilities',
  interfaceMode: 'headless-ready',
  capabilities: [
    { id: 'C1', name: 'Customer Segmentation' },
    { id: 'C2', name: 'Retention Risk' },
    { id: 'C3', name: 'Promotion Recommender' },
    { id: 'C4', name: 'Next-Best-Action' },
    { id: 'C5', name: 'Feedback & Sentiment' }
  ],
  reads: [
    { domain: 'shared-customer', resource: 'customers', owner: 'platform' },
    { domain: 'sales', resource: 'transactions', owner: 'sales-agent' },
    { domain: 'inventory', resource: 'products.stock', owner: 'inventory-agent' },
    { domain: 'pricing', resource: 'products.price-and-margin', owner: 'pricing-or-finance-agent' },
    { domain: 'customer-engagement', resource: 'feedback', owner: 'customer-engagement-or-platform' }
  ],
  writes: [
    { resource: 'insights', ownership: 'customer-engagement' },
    { resource: 'events', ownership: 'shared-event-stream' }
  ],
  consumesEvents: CUSTOMER_ENGAGEMENT_INPUT_EVENTS,
  publishesEvents: Object.values(CUSTOMER_ENGAGEMENT_EVENT_TYPES),
  invariants: [
    'Never owns or decrements inventory.',
    'Never changes authoritative product pricing.',
    'Never writes sales transactions.',
    'Promotional recommendations require customer marketing consent.',
    'Every read/write is scoped by businessId.',
    'The final platform supplies authentication, Firebase configuration and the shared user interface.'
  ]
} as const;
