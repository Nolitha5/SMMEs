import { deleteDoc, doc, setDoc } from 'firebase/firestore';
import { db } from './db';
import { firebaseEnabled, getFirebaseServices } from './firebase';

export interface SyncResult { attempted: number; synced: number; failed: number; message: string; }

export async function flushSyncQueue(): Promise<SyncResult> {
  if (!firebaseEnabled) return { attempted: 0, synced: 0, failed: 0, message: 'Firebase is disabled; data remains safely stored on this device.' };
  if (!navigator.onLine) return { attempted: 0, synced: 0, failed: 0, message: 'Device is offline; queued changes will remain local.' };
  const services = getFirebaseServices();
  if (!services) return { attempted: 0, synced: 0, failed: 0, message: 'Firebase is not configured.' };
  if (!services.auth.currentUser) return { attempted: 0, synced: 0, failed: 0, message: 'Firebase is configured, but the shared platform has not authenticated a user yet.' };

  const items = await db.syncQueue.toArray();
  let synced = 0, failed = 0;
  for (const item of items) {
    try {
      await db.syncQueue.update(item.id, { status: 'syncing', updatedAt: new Date().toISOString() });
      const ref = doc(services.db, 'businesses', item.businessId, item.collection, item.docId);
      if (item.operation === 'delete') await deleteDoc(ref);
      else await setDoc(ref, item.payload, { merge: true });
      await db.transaction('rw', [db.syncQueue, db.syncAudit], async () => {
        await db.syncAudit.put({ id: `audit-${item.id}`, businessId: item.businessId, queueId: item.id, collection: item.collection, docId: item.docId, syncedAt: new Date().toISOString() });
        await db.syncQueue.delete(item.id);
      });
      synced++;
    } catch (error) {
      failed++;
      const message = error instanceof Error ? error.message : String(error);
      await db.syncQueue.update(item.id, { status: 'failed', attempts: item.attempts + 1, lastError: message, updatedAt: new Date().toISOString() });
    }
  }
  return { attempted: items.length, synced, failed, message: failed ? `${synced} synced; ${failed} still queued.` : `${synced} queued change${synced === 1 ? '' : 's'} synced.` };
}
