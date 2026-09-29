import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { loadWorkspace } from './lib/api';
import type { Workspace } from './types';

type WorkspaceContextValue = {
  data: Workspace | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const Context = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loadWorkspace());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, []);

  return <Context.Provider value={{ data, loading, error, refresh }}>{children}</Context.Provider>;
}

export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return value;
}
