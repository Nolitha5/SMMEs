import { useEffect, useState } from 'react';
import { seedDemoData } from '../lib/repository';
import { flushSyncQueue } from '../lib/sync';

export function useBootstrap() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    void navigator.storage?.persist?.().catch(() => false);
    const enableSampleData = import.meta.env.VITE_ENABLE_DEMO_DATA === 'true';
    (enableSampleData ? seedDemoData() : Promise.resolve()).finally(() => setReady(true));
    const onOnline = () => { void flushSyncQueue(); };
    window.addEventListener('online', onOnline);
    return () => window.removeEventListener('online', onOnline);
  }, []);
  return ready;
}
