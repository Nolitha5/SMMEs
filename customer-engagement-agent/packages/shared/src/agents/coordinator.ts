import type { Customer, CustomerCycleResult, Feedback, Product, Transaction } from '../types.js';
import { runSegmentation } from './c1-segmentation.js';
import { runFeedbackAnalysis } from './c5-feedback.js';
import { runChurnRisk } from './c2-churn.js';
import { runPromotionRecommendation } from './c3-promotion.js';
import { runNextBestAction } from './c4-next-action.js';

export function runCustomerCycle(customer: Customer, transactions: Transaction[], products: Product[], feedback: Feedback[], nowIso = new Date().toISOString()): CustomerCycleResult {
  const segment = runSegmentation(customer, transactions, nowIso);
  const feedbackResult = runFeedbackAnalysis(customer.id, feedback);
  const churn = runChurnRisk(segment, feedbackResult);
  const promotion = runPromotionRecommendation(customer, segment, transactions, products);
  const nextAction = runNextBestAction(customer, segment, churn, promotion, feedbackResult);
  return { customerId: customer.id, segment, feedback: feedbackResult, churn, promotion, nextAction };
}

export function runBusinessCycle(customers: Customer[], transactions: Transaction[], products: Product[], feedback: Feedback[], nowIso = new Date().toISOString()): CustomerCycleResult[] {
  return customers.map(customer => runCustomerCycle(customer, transactions, products, feedback, nowIso));
}
