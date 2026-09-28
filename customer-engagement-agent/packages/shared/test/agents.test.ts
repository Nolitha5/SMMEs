import { describe, expect, it } from 'vitest';
import { demoData, runBusinessCycle, runCustomerCycle, runFeedbackAnalysis, runPromotionRecommendation, runSegmentation } from '../src/index.js';

const now = new Date('2026-09-28T12:00:00.000Z');
const data = demoData(now);

describe('Customer Engagement engines', () => {
  it('segments a high-frequency customer as champion', () => {
    const customer = data.customers.find(c => c.id === 'cus-kagiso')!;
    expect(runSegmentation(customer, data.transactions, now.toISOString()).segment).toBe('champion');
  });

  it('detects dormant customers', () => {
    const customer = data.customers.find(c => c.id === 'cus-themba')!;
    expect(runSegmentation(customer, data.transactions, now.toISOString()).segment).toBe('dormant');
  });

  it('detects negative feedback topics', () => {
    const result = runFeedbackAnalysis('cus-sipho', data.feedback);
    expect(result.sentiment).toBe('negative');
    expect(result.topics).toContain('service');
  });

  it('blocks marketing offers without consent', () => {
    const customer = data.customers.find(c => c.id === 'cus-lerato')!;
    const segment = runSegmentation(customer, data.transactions, now.toISOString());
    expect(runPromotionRecommendation(customer, segment, data.transactions, data.products).eligible).toBe(false);
  });

  it('prioritises service recovery for priority negative feedback', () => {
    const customer = data.customers.find(c => c.id === 'cus-sipho')!;
    const result = runCustomerCycle(customer, data.transactions, data.products, data.feedback, now.toISOString());
    expect(result.nextAction.action).toBe('service-recovery');
    expect(result.nextAction.priority).toBe('high');
  });

  it('runs all five capabilities for every customer', () => {
    const results = runBusinessCycle(data.customers, data.transactions, data.products, data.feedback, now.toISOString());
    expect(results).toHaveLength(data.customers.length);
    expect(results.every(r => r.segment.agentId === 'C1' && r.churn.agentId === 'C2' && r.promotion.agentId === 'C3' && r.nextAction.agentId === 'C4' && r.feedback.agentId === 'C5')).toBe(true);
  });
});
