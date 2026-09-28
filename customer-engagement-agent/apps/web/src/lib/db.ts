import Dexie, { type EntityTable } from 'dexie';
import type { AgentEvent, Customer, Feedback, Insight, Product, SyncQueueItem, Transaction } from '@cea/shared';

export interface MetaRecord { key: string; value: string; }
export interface SyncAudit { id: string; businessId: string; queueId: string; collection: string; docId: string; syncedAt: string; }

class EngagementDB extends Dexie {
  customers!: EntityTable<Customer, 'id'>;
  transactions!: EntityTable<Transaction, 'id'>;
  products!: EntityTable<Product, 'id'>;
  feedback!: EntityTable<Feedback, 'id'>;
  insights!: EntityTable<Insight, 'id'>;
  events!: EntityTable<AgentEvent, 'id'>;
  syncQueue!: EntityTable<SyncQueueItem, 'id'>;
  syncAudit!: EntityTable<SyncAudit, 'id'>;
  meta!: EntityTable<MetaRecord, 'key'>;

  constructor() {
    super('customer-engagement-agent');
    this.version(1).stores({
      customers: 'id, businessId, name, lastVisitAt',
      transactions: 'id, businessId, customerId, createdAt',
      products: 'id, businessId, category, stock, isActive',
      feedback: 'id, businessId, customerId, createdAt, status',
      insights: 'id, businessId, customerId, agentId, createdAt',
      events: 'id, businessId, name, producer, status, createdAt',
      syncQueue: 'id, businessId, status, collection, createdAt',
      syncAudit: 'id, businessId, queueId, syncedAt',
      meta: 'key'
    });
  }
}

export const db = new EngagementDB();
