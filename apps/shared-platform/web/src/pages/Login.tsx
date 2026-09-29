import { FormEvent, useEffect, useState } from 'react';
import { signInWithEmailAndPassword, type Auth } from 'firebase/auth';
import { Navigate, useNavigate } from 'react-router-dom';
import { authMode, ensureClientAuth } from '../lib/firebase';

export function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [auth, setAuth] = useState<Auth | null>(null);
  const [checking, setChecking] = useState(authMode === 'firebase');

  useEffect(() => {
    if (authMode !== 'firebase') { setChecking(false); return; }
    void ensureClientAuth().then((next) => { setAuth(next); setChecking(false); }).catch(() => setChecking(false));
  }, []);

  if (authMode === 'local') return <Navigate to="/" replace />;
  if (checking) return <div className="auth-check">Preparing sign in…</div>;

  if (!auth) {
    return (
      <div className="login-shell">
        <div className="login-panel">
          <span className="eyebrow orange">Connection required</span>
          <h1>Workspace sign in is unavailable.</h1>
          <p>This installation is missing its sign in configuration. Ask the workspace administrator to reconnect it.</p>
        </div>
      </div>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await signInWithEmailAndPassword(auth!, email, password);
      navigate('/');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <div className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <div className="login-brand"><strong>SME Operations</strong></div>
        <span className="eyebrow orange">Business workspace</span>
        <h1>Sign in</h1>
        <p>Use the account that belongs to this business workspace.</p>
        <label className="field"><span>Email</span><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="field"><span>Password</span><input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error ? <div className="form-error">{error}</div> : null}
        <button className="button primary wide" type="submit">Sign in</button>
      </form>
    </div>
  );
}
