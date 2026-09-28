import type { Feedback, FeedbackResult } from '../types.js';
import { clamp } from '../utils.js';

const positive = ['good', 'great', 'excellent', 'friendly', 'helpful', 'fresh', 'fast', 'love', 'happy', 'clean', 'thank'];
const negative = ['bad', 'poor', 'rude', 'slow', 'expensive', 'broken', 'stale', 'dirty', 'angry', 'refund', 'wrong', 'problem', 'complaint', 'unhappy', 'never again', 'unsafe', 'sick', 'fraud', 'stolen'];
const priorityWords = ['refund', 'angry', 'never again', 'unsafe', 'sick', 'fraud', 'stolen'];
const topicWords: Record<string, string[]> = {
  service: ['rude', 'friendly', 'helpful', 'slow', 'fast', 'service', 'staff', 'queue'],
  price: ['price', 'expensive', 'cheap', 'discount', 'cost'],
  stock: ['stock', 'sold out', 'available', 'shelf'],
  quality: ['fresh', 'stale', 'broken', 'quality', 'dirty'],
  payment: ['card', 'cash', 'payment', 'refund', 'change'],
  delivery: ['delivery', 'driver', 'late', 'order']
};

export function runFeedbackAnalysis(customerId: string, feedback: Feedback[]): FeedbackResult {
  const own = feedback.filter(f => f.customerId === customerId);
  if (!own.length) {
    return { agentId: 'C5', customerId, sentiment: 'neutral', sentimentScore: 50, topics: [], urgency: 'normal', reasons: ['No customer feedback recorded yet.'] };
  }
  const text = own.map(f => f.message.toLowerCase()).join(' ');
  const positiveHits = positive.reduce((n, word) => n + (text.includes(word) ? 1 : 0), 0);
  const negativeHits = negative.reduce((n, word) => n + (text.includes(word) ? 1 : 0), 0);
  const delta = positiveHits - negativeHits;
  const sentimentScore = clamp(50 + delta * 12);
  const sentiment = sentimentScore >= 62 ? 'positive' : sentimentScore <= 38 ? 'negative' : 'neutral';
  const topics = Object.entries(topicWords).filter(([, words]) => words.some(word => text.includes(word))).map(([topic]) => topic);
  const urgency = priorityWords.some(word => text.includes(word)) ? 'priority' : 'normal';
  const reasons = [`Analysed ${own.length} feedback item${own.length === 1 ? '' : 's'}.`];
  if (positiveHits) reasons.push(`${positiveHits} positive signal${positiveHits === 1 ? '' : 's'} detected.`);
  if (negativeHits) reasons.push(`${negativeHits} negative signal${negativeHits === 1 ? '' : 's'} detected.`);
  if (topics.length) reasons.push(`Topics: ${topics.join(', ')}.`);
  return { agentId: 'C5', customerId, sentiment, sentimentScore, topics, urgency, reasons };
}
