import { executeCustomerEngagementCycle } from '../../../../vendor/customer-engagement-shared/dist/integration/runtime.js';
import { makeResult, parseDate } from './common.mjs';

function latest(values) {
  return values.map(parseDate).filter(Boolean).sort((a, b) => b.getTime() - a.getTime())[0] || null;
}
function earliest(values) {
  return values.map(parseDate).filter(Boolean).sort((a, b) => a.getTime() - b.getTime())[0] || null;
}

function mapTransactions(rows, businessId) {
  const grouped = new Map();
  for (const row of rows || []) {
    if (!row.customer_id) continue;
    const key = String(row.transaction_id);
    if (!grouped.has(key)) grouped.set(key, { id: key, businessId, customerId: String(row.customer_id), total: 0, items: [], createdAt: row.timestamp, sourceAgent: 'Sales' });
    const tx = grouped.get(key);
    const qty = Number(row.qty || 0), price = Number(row.unit_price || 0);
    tx.items.push({ productId: String(row.product_id), quantity: qty, unitPrice: price });
    tx.total += qty * price;
    if ((parseDate(row.timestamp)?.getTime() || 0) > (parseDate(tx.createdAt)?.getTime() || 0)) tx.createdAt = row.timestamp;
  }
  return [...grouped.values()];
}

export async function runCustomerDomain({ businessId, customers, transactions, products, feedback, inventoryByProduct, now = new Date() }) {
  const mappedTransactions = mapTransactions(transactions, businessId);
  const txByCustomer = new Map();
  for (const tx of mappedTransactions) {
    if (!txByCustomer.has(tx.customerId)) txByCustomer.set(tx.customerId, []);
    txByCustomer.get(tx.customerId).push(tx);
  }

  const mappedCustomers = (customers || []).map((customer) => {
    const own = txByCustomer.get(String(customer.customer_id)) || [];
    const times = own.map((x) => x.createdAt);
    const first = earliest(times), last = latest(times);
    return {
      id: String(customer.customer_id), businessId,
      name: customer.name || String(customer.customer_id), phone: customer.phone || undefined,
      consentMarketing: Boolean(customer.consent_marketing), tags: Array.isArray(customer.tags) ? customer.tags : [],
      createdAt: customer.created_at || first?.toISOString() || customer.last_visit_at || now.toISOString(),
      lastVisitAt: customer.last_visit_at || last?.toISOString() || undefined
    };
  });

  const mappedProducts = (products || []).filter((p) => p.active !== false).map((product) => {
    const inv = inventoryByProduct.get(String(product.product_id)) || {};
    const stock = Number(inv.I1?.available_stock || 0);
    const reorderLevel = Number(inv.I2?.reorder_point || 0);
    const price = Number(product.sell_price || 0), cost = Number(product.unit_cost || 0) + Number(product.variable_fees_per_unit || 0);
    const marginPct = price > 0 ? ((price - cost) / price) * 100 : 0;
    return {
      id: String(product.product_id), businessId, name: product.name || String(product.product_id), sku: product.sku || String(product.product_id), category: product.category || '',
      stock, reorderLevel, marginPct, price, isActive: product.active !== false, sourceAgent: 'Pricing'
    };
  });

  const mappedFeedback = (feedback || []).map((item) => ({
    id: String(item.feedback_id), businessId, customerId: String(item.customer_id),
    channel: String(item.channel || 'OTHER').toLowerCase().replace('_', '-'), message: String(item.message || ''), createdAt: item.created_at,
    status: String(item.status || 'NEW').toLowerCase()
  }));

  const writes = { insights: [], events: [] };
  const port = {
    async readCustomers() { return mappedCustomers; },
    async readTransactions() { return mappedTransactions; },
    async readProducts() { return mappedProducts; },
    async readFeedback() { return mappedFeedback; },
    async writeInsights(_businessId, rows) { writes.insights.push(...rows); },
    async publishEvents(_businessId, rows) { writes.events.push(...rows); }
  };

  if (!mappedCustomers.length) return { results: [], artifacts: { insights: [], events: [] }, recommendations: [] };
  const cycle = await executeCustomerEngagementCycle(port, businessId, now.toISOString());
  const results = [];
  const recommendations = [];

  for (const row of cycle.results) {
    const pieces = [row.segment, row.churn, row.promotion, row.nextAction, row.feedback];
    for (const piece of pieces) {
      const cap = piece.agentId;
      const outputType = cap === 'C1' ? 'CustomerSegment' : cap === 'C2' ? 'RetentionRisk' : cap === 'C3' ? 'PromotionRecommendation' : cap === 'C4' ? 'CustomerAction' : 'FeedbackInsight';
      const confidence = cap === 'C1' ? Math.min(0.95, 0.5 + Number(piece.score || 0) / 200) : cap === 'C2' ? 0.85 : cap === 'C3' ? (piece.eligible ? Math.min(0.9, 0.5 + Number(piece.score || 0) / 200) : 0.7) : cap === 'C5' ? 0.85 : 0.85;
      const riskLevel = cap === 'C2' ? (['critical', 'high'].includes(piece.riskBand) ? 'HIGH' : piece.riskBand === 'medium' ? 'MEDIUM' : 'LOW') : cap === 'C4' ? (piece.priority === 'high' ? 'HIGH' : piece.priority === 'medium' ? 'MEDIUM' : 'LOW') : cap === 'C5' && piece.urgency === 'priority' ? 'HIGH' : cap === 'C3' && piece.eligible ? 'MEDIUM' : 'LOW';
      results.push(makeResult({ capabilityId: cap, domain: 'customer-engagement', outputType, entityType: 'customer', entityId: row.customerId, payload: piece, confidence, riskLevel, inputRefs: cap === 'C1' ? ['customers', 'transactions'] : cap === 'C2' ? ['C1', 'C5'] : cap === 'C3' ? ['C1', 'products', 'transactions'] : cap === 'C4' ? ['C1', 'C2', 'C3', 'C5'] : ['feedback'] }));
    }
    if (row.nextAction.action !== 'no-action' && row.nextAction.priority !== 'low') {
      recommendations.push({ capabilityId: 'C4', domain: 'customer-engagement', recommendationType: 'Customer action', subjectType: 'customer', subjectId: row.customerId, action: row.nextAction, confidence: 0.85, riskLevel: row.nextAction.priority === 'high' ? 'HIGH' : 'MEDIUM' });
    }
  }

  return { results, artifacts: writes, recommendations };
}
