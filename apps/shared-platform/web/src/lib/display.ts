export function friendlyEventName(value?: string) {
  if (!value) return 'Activity';
  const stripped = value.replace(/\.v\d+$/i, '');
  const map: Record<string, string> = {
    'demand.forecast.updated': 'Demand forecast updated',
    'inventory.stock.updated': 'Stock position updated',
    'procurement.supplier-performance.updated': 'Supplier performance updated',
    'pricing.recommendation.created': 'Price recommendation created',
    'procurement.recommendation.created': 'Purchase recommendation created',
    'governance.recommendation.approved': 'Approved action applied',
    'customer.segment.updated': 'Customer segment updated',
    'customer.retention-risk.changed': 'Retention risk updated',
    'customer.promotion.recommended': 'Customer promotion recommended',
    'customer.feedback-insight.created': 'Customer feedback reviewed',
    'customer.next-action.recommended': 'Customer action recommended'
  };
  return map[stripped] || stripped.replaceAll('.', ' ').replaceAll('_', ' ').replaceAll('-', ' ').replace(/\s+/g, ' ').trim().toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

export function friendlySource(value?: string, capabilities?: Array<{ capabilityId: string; name: string }>) {
  if (!value) return 'Platform';
  const cap = capabilities?.find((item) => item.capabilityId === value);
  if (cap) return cap.name;
  if (value === 'platform-governance') return 'Approvals';
  return value.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\s+/g, ' ').trim().replace(/\b\w/g, (c) => c.toUpperCase());
}
