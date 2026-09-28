import type { ChurnResult, FeedbackResult, SegmentResult } from '../types.js';
import { clamp } from '../utils.js';

export function runChurnRisk(segment: SegmentResult, feedback: FeedbackResult): ChurnResult {
  let score = 10;
  const reasons: string[] = [];
  const recency = segment.metrics.recencyDays;

  score += Math.min(recency, 100) * 0.65;
  if (segment.segment === 'at-risk') { score += 15; reasons.push('C1 classified the customer as at-risk.'); }
  if (segment.segment === 'dormant') { score += 25; reasons.push('C1 classified the customer as dormant.'); }
  if (segment.metrics.frequency90d >= 5) { score -= 10; reasons.push('Frequent recent purchases reduce churn risk.'); }
  if (feedback.sentiment === 'negative') { score += 18; reasons.push('Recent feedback sentiment is negative.'); }
  if (feedback.urgency === 'priority') { score += 12; reasons.push('Feedback contains a priority service signal.'); }
  if (!reasons.length) reasons.push('No strong churn indicators beyond recency were found.');

  const riskScore = clamp(score);
  const riskBand = riskScore >= 80 ? 'critical' : riskScore >= 60 ? 'high' : riskScore >= 35 ? 'medium' : 'low';
  return { agentId: 'C2', customerId: segment.customerId, riskScore, riskBand, reasons };
}
