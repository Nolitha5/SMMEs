import React, { useState } from 'react';
import { getFirebaseAuth } from '../firebase.js';
const h = React.createElement;

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const auth = await getFirebaseAuth();
      const { signInWithEmailAndPassword } = await import('firebase/auth');
      await signInWithEmailAndPassword(auth, email, password);
    } catch (err) { setError(err.message || 'Login failed'); }
    finally { setBusy(false); }
  }

  return h('div', { className: 'min-h-screen grid place-items-center bg-slate-950 px-4' },
    h('form', { onSubmit: submit, className: 'w-full max-w-md rounded-2xl bg-white p-7 shadow-xl' },
      h('p', { className: 'text-xs font-bold uppercase tracking-[0.2em] text-slate-500' }, 'Agent 4 · Procurement'),
      h('h1', { className: 'mt-2 text-2xl font-bold' }, 'Manager sign in'),
      h('p', { className: 'mt-2 text-sm text-slate-600' }, 'Firebase Authentication protects staging access.'),
      error ? h('div', { className: 'mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700' }, error) : null,
      h('label', { className: 'mt-5 block text-sm font-semibold' }, 'Email'),
      h('input', { className: 'input mt-1', type: 'email', value: email, onChange: e => setEmail(e.target.value), required: true }),
      h('label', { className: 'mt-4 block text-sm font-semibold' }, 'Password'),
      h('input', { className: 'input mt-1', type: 'password', value: password, onChange: e => setPassword(e.target.value), required: true }),
      h('button', { className: 'btn-primary mt-6 w-full', disabled: busy }, busy ? 'Signing in…' : 'Sign in')
    )
  );
}
