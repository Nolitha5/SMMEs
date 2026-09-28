import type { Customer, Product, PromotionResult, SegmentResult, Transaction } from '../types.js';
import { clamp } from '../utils.js';

export function runPromotionRecommendation(customer: Customer, segment: SegmentResult, transactions: Transaction[], products: Product[]): PromotionResult {
  if (!customer.consentMarketing) {
    return { agentId: 'C3', customerId: customer.id, eligible: false, score: 0, reasons: ['Customer has not consented to marketing offers.'] };
  }

  const purchased = new Map<string, number>();
  transactions.filter(t => t.customerId === customer.id).forEach(t => t.items.forEach(item => purchased.set(item.productId, (purchased.get(item.productId) ?? 0) + item.quantity)));
  const candidates = products
    .filter(p => p.isActive && p.stock > Math.max(p.reorderLevel * 1.5, p.reorderLevel + 3) && p.marginPct >= 12)
    .map(product => {
      const affinity = Math.min((purchased.get(product.id) ?? 0) * 7, 35);
      const stockHealth = Math.min(((product.stock - product.reorderLevel) / Math.max(product.reorderLevel, 1)) * 12, 30);
      const margin = Math.min(product.marginPct, 35);
      return { product, score: affinity + stockHealth + margin };
    })
    .sort((a, b) => b.score - a.score);

  if (!candidates.length) {
    return { agentId: 'C3', customerId: customer.id, eligible: false, score: 0, reasons: ['No promotion candidate passes stock and margin guardrails.'] };
  }

  const winner = candidates[0];
  const baseOffer = segment.segment === 'at-risk' || segment.segment === 'dormant' ? 10 : segment.segment === 'value-seeker' ? 8 : 5;
  const maxSafeOffer = Math.max(3, Math.floor(winner.product.marginPct * 0.45));
  const offerPct = Math.min(baseOffer, maxSafeOffer);
  return {
    agentId: 'C3', customerId: customer.id, eligible: true,
    productId: winner.product.id, productName: winner.product.name, offerPct,
    score: clamp(winner.score),
    reasons: ['Product is safely above its reorder threshold.', `Margin guardrail allows up to the recommended ${offerPct}% offer.`, purchased.has(winner.product.id) ? 'Customer has bought this product before.' : 'Candidate chosen from healthy stock with acceptable margin.']
  };
}
