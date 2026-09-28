import type { ChurnResult, Customer, FeedbackResult, NextActionResult, PromotionResult, SegmentResult } from '../types.js';

export function runNextBestAction(customer: Customer, segment: SegmentResult, churn: ChurnResult, promotion: PromotionResult, feedback: FeedbackResult): NextActionResult {
  if (feedback.sentiment === 'negative' && feedback.urgency === 'priority') {
    return { agentId: 'C4', customerId: customer.id, action: 'service-recovery', priority: 'high', channel: 'whatsapp', summary: 'Review the complaint and contact the customer before sending any promotion.', reasons: ['C5 found negative priority feedback.', 'Service recovery takes precedence over promotion.'] };
  }
  if (churn.riskBand === 'critical' || churn.riskBand === 'high') {
    return { agentId: 'C4', customerId: customer.id, action: promotion.eligible ? 'retention-offer' : 'service-recovery', priority: 'high', channel: customer.consentMarketing ? 'whatsapp' : 'in-store', summary: promotion.eligible ? `Consider a ${promotion.offerPct}% retention offer on ${promotion.productName}.` : 'Use a non-promotional personal follow-up to understand why visits stopped.', reasons: [`C2 risk is ${churn.riskBand}.`, 'The action respects marketing consent.'] };
  }
  if (promotion.eligible && ['regular', 'value-seeker', 'new'].includes(segment.segment)) {
    return { agentId: 'C4', customerId: customer.id, action: 'promotion', priority: 'medium', channel: 'whatsapp', summary: `Offer ${promotion.offerPct}% on ${promotion.productName} during the next eligible campaign.`, reasons: ['C3 found a stock-safe, margin-safe promotion.', `C1 segment is ${segment.segment}.`] };
  }
  if (segment.segment === 'champion' || segment.segment === 'loyal') {
    return { agentId: 'C4', customerId: customer.id, action: 'loyalty-thanks', priority: 'low', channel: customer.consentMarketing ? 'whatsapp' : 'in-store', summary: 'Thank the customer for their loyalty; avoid unnecessary discounting.', reasons: ['Strong customer value means recognition is preferable to automatic discounting.'] };
  }
  return { agentId: 'C4', customerId: customer.id, action: 'feedback-request', priority: 'low', channel: customer.consentMarketing ? 'sms' : 'in-store', summary: 'Ask for lightweight feedback on the next interaction.', reasons: ['No urgent retention or promotion action is needed.'] };
}
