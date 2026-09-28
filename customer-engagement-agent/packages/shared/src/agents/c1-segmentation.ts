import type { Customer, SegmentResult, Transaction } from '../types.js';
import { clamp, daysBetween } from '../utils.js';

export function runSegmentation(customer: Customer, transactions: Transaction[], nowIso = new Date().toISOString()): SegmentResult {
  const own = transactions.filter(t => t.customerId === customer.id);
  const recent = own.filter(t => daysBetween(t.createdAt, nowIso) <= 90);
  const latest = own.map(t => t.createdAt).sort().at(-1) ?? customer.lastVisitAt ?? customer.createdAt;
  const recencyDays = daysBetween(latest, nowIso);
  const frequency90d = recent.length;
  const spend90d = recent.reduce((sum, t) => sum + t.total, 0);
  const avgBasket = frequency90d ? spend90d / frequency90d : 0;

  let segment: SegmentResult['segment'];
  const reasons: string[] = [];

  if (recencyDays > 90) {
    segment = 'dormant';
    reasons.push(`No recorded purchase for ${recencyDays} days.`);
  } else if (recencyDays > 45) {
    segment = 'at-risk';
    reasons.push(`Last purchase was ${recencyDays} days ago.`);
  } else if (frequency90d >= 8 && spend90d >= 1200) {
    segment = 'champion';
    reasons.push('High recent frequency and spend.');
  } else if (frequency90d >= 5) {
    segment = 'loyal';
    reasons.push('Returns frequently within the last 90 days.');
  } else if (own.length <= 1 && recencyDays <= 30) {
    segment = 'new';
    reasons.push('Recently acquired customer with limited history.');
  } else if (avgBasket > 0 && avgBasket < 90 && frequency90d >= 2) {
    segment = 'value-seeker';
    reasons.push('Frequent lower-value baskets indicate price sensitivity.');
  } else {
    segment = 'regular';
    reasons.push('Stable purchasing pattern without extreme recency/frequency signals.');
  }

  const score = clamp((Math.max(0, 60 - recencyDays) / 60) * 40 + Math.min(frequency90d / 8, 1) * 30 + Math.min(spend90d / 1200, 1) * 30);
  return { agentId: 'C1', customerId: customer.id, segment, score, reasons, metrics: { recencyDays, frequency90d, spend90d } };
}
