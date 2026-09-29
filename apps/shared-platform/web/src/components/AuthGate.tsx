import { useEffect, useState, type ReactNode } from 'react';
import { onAuthStateChanged, type User } from 'firebase/auth';
import { Navigate } from 'react-router-dom';
import { authMode, ensureClientAuth } from '../lib/firebase';

export function AuthGate({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(authMode === 'firebase');
  const [configured, setConfigured] = useState(authMode !== 'firebase');

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    let active = true;
    if (authMode !== 'firebase') {
      setChecking(false);
      return;
    }
    void ensureClientAuth().then((auth) => {
      if (!active) return;
      if (!auth) {
        setConfigured(false);
        setChecking(false);
        return;
      }
      setConfigured(true);
      unsubscribe = onAuthStateChanged(auth, (next) => {
        if (!active) return;
        setUser(next);
        setChecking(false);
      });
    }).catch(() => {
      if (active) { setConfigured(false); setChecking(false); }
    });
    return () => { active = false; unsubscribe?.(); };
  }, []);

  if (authMode === 'local') return children;
  if (checking) return <div className="auth-check">Checking session…</div>;
  if (!configured || !user) return <Navigate to="/login" replace />;
  return children;
}
