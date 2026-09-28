import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api, uploadCsv } from './api.js';
import { getFirebaseAuth } from './firebase.js';
import Badge from './components/Badge.js';
import Login from './components/Login.js';

const h = React.createElement;
const money = v => `R ${Number(v || 0).toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = v => `${Math.round(Number(v || 0) * 100)}%`;

function ErrorBox({ error }) {
  return error ? h('div', { className: 'mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700' }, error) : null;
}

function Stat({ label, value, hint }) {
  return h('div', { className: 'card' },
    h('p', { className: 'text-xs font-semibold uppercase tracking-wide text-slate-500' }, label),
    h('p', { className: 'mt-2 text-3xl font-bold text-slate-950' }, value),
    hint ? h('p', { className: 'mt-2 text-xs text-slate-500' }, hint) : null,
  );
}

function Dashboard({ refreshKey }) {
  const [data, setData] = useState(null); const [error, setError] = useState('');
  useEffect(() => { api('/dashboard').then(setData).catch(e => setError(e.message)); }, [refreshKey]);
  if (!data) return h('div', null, h(ErrorBox, { error }), 'Loading dashboard…');
  return h('div', null,
    h(ErrorBox, { error }),
    h('div', { className: 'grid gap-4 sm:grid-cols-2 xl:grid-cols-5' },
      h(Stat, { label: 'Active suppliers', value: data.active_suppliers }),
      h(Stat, { label: 'Pending approvals', value: data.pending_approvals }),
      h(Stat, { label: 'Open POs', value: data.open_purchase_orders }),
      h(Stat, { label: 'Exceptions', value: data.procurement_exceptions }),
      h(Stat, { label: 'PO value', value: money(data.purchase_order_value) }),
    ),
    h('div', { className: 'mt-6 grid gap-5 lg:grid-cols-2' },
      h('div', { className: 'card' },
        h('h2', { className: 'text-lg font-bold' }, 'Five-agent procurement domain'),
        h('p', { className: 'mt-1 text-sm text-slate-600' }, 'R1–R5 remain independently testable and are coordinated through stable contracts.'),
        h('div', { className: 'mt-4 space-y-3' }, ...data.agent_status.map(a =>
          h('div', { key: a.agent_id, className: 'flex items-center justify-between rounded-xl bg-slate-50 p-3' },
            h('div', null, h('p', { className: 'font-semibold' }, `${a.agent_id} · ${a.name}`), h('p', { className: 'text-xs text-slate-500' }, `v${a.version}`)),
            h(Badge, { value: a.last_error ? 'ERROR' : 'READY' }),
          )
        ))
      ),
      h('div', { className: 'card' },
        h('h2', { className: 'text-lg font-bold' }, 'Architecture controls'),
        h('ul', { className: 'mt-4 space-y-3 text-sm text-slate-700' },
          h('li', null, '• Human approval is mandatory for R4 purchase recommendations.'),
          h('li', null, '• Missing or stale Demand/Inventory contracts fail safely as insufficient evidence.'),
          h('li', null, '• R5 performs deterministic PO ↔ receipt ↔ invoice reconciliation.'),
          h('li', null, '• Every agent output stores evidence, confidence, risk, rule version and approval state.'),
          h('li', null, '• Closed procurement outcomes feed R2 reliability and R3 lead-time history.'),
        )
      )
    )
  );
}

function Suppliers({ refreshKey }) {
  const [rows, setRows] = useState([]); const [score, setScore] = useState(null); const [error, setError] = useState('');
  useEffect(() => { api('/data/suppliers').then(setRows).catch(e => setError(e.message)); }, [refreshKey]);
  async function inspect(id) { setError(''); try { setScore(await api(`/suppliers/${id}/scorecard`)); } catch (e) { setError(e.message); } }
  return h('div', null,
    h(ErrorBox, { error }),
    h('div', { className: 'card overflow-x-auto' },
      h('div', { className: 'mb-4' }, h('h2', { className: 'text-lg font-bold' }, 'Supplier intelligence'), h('p', { className: 'text-sm text-slate-600' }, 'R2 reliability and R3 lead-time risk are calculated from auditable supplier outcomes.')),
      h('table', { className: 'w-full min-w-[700px]' },
        h('thead', { className: 'border-b text-left text-xs uppercase text-slate-500' }, h('tr', null,
          ...['Supplier', 'Status', 'Terms', 'Currency', 'Action'].map(x => h('th', { key: x, className: 'table-cell' }, x))
        )),
        h('tbody', null, ...rows.map(r => h('tr', { key: r.supplier_id, className: 'border-b last:border-0' },
          h('td', { className: 'table-cell' }, h('p', { className: 'font-semibold' }, r.name), h('p', { className: 'text-xs text-slate-500' }, r.supplier_id)),
          h('td', { className: 'table-cell' }, h(Badge, { value: r.status })),
          h('td', { className: 'table-cell' }, `${r.payment_terms_days} days`),
          h('td', { className: 'table-cell' }, r.currency),
          h('td', { className: 'table-cell' }, h('button', { className: 'btn-secondary', onClick: () => inspect(r.supplier_id) }, 'View scorecard'))
        )))
      )
    ),
    score ? h('div', { className: 'mt-5 grid gap-4 lg:grid-cols-2' },
      h('div', { className: 'card' },
        h('h3', { className: 'font-bold' }, `R2 · ${score.supplier.name}`),
        h('p', { className: 'mt-4 text-4xl font-bold' }, pct(score.reliability.score)),
        h('div', { className: 'mt-4 grid grid-cols-2 gap-3 text-sm' },
          h('div', null, 'On-time', h('strong', { className: 'block' }, pct(score.reliability.on_time_rate))),
          h('div', null, 'Fill rate', h('strong', { className: 'block' }, pct(score.reliability.fill_rate))),
          h('div', null, 'Defect rate', h('strong', { className: 'block' }, pct(score.reliability.defect_rate))),
          h('div', null, 'Evidence confidence', h('strong', { className: 'block' }, pct(score.reliability.confidence))),
        )
      ),
      h('div', { className: 'card' },
        h('h3', { className: 'font-bold' }, 'R3 · Lead-time risk'),
        h('div', { className: 'mt-3' }, h(Badge, { value: score.lead_time.risk })),
        h('div', { className: 'mt-4 grid grid-cols-2 gap-3 text-sm' },
          h('div', null, 'Expected', h('strong', { className: 'block' }, `${score.lead_time.expected_days} days`)),
          h('div', null, 'P90', h('strong', { className: 'block' }, `${score.lead_time.p90_days} days`)),
          h('div', null, 'Delay rate', h('strong', { className: 'block' }, pct(score.lead_time.delay_rate))),
          h('div', null, 'Sample size', h('strong', { className: 'block' }, score.lead_time.sample_size)),
        )
      )
    ) : null
  );
}

function Recommendations({ refreshKey, onChanged }) {
  const [rows, setRows] = useState([]); const [product, setProduct] = useState('SKU-100'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const load = useCallback(() => api('/recommendations').then(setRows).catch(e => setError(e.message)), []);
  useEffect(() => { load(); }, [load, refreshKey]);
  async function generate() { setBusy(true); setError(''); try { await api(`/procurement/recommend/${product}`, { method: 'POST' }); await load(); onChanged(); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  async function decide(id, decision) { setError(''); try { await api(`/recommendations/${id}/decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, reason: `Manager ${decision.toLowerCase()} via procurement dashboard` }) }); await load(); onChanged(); } catch (e) { setError(e.message); } }
  async function execute(id) { setError(''); try { await api(`/recommendations/${id}/execute`, { method: 'POST' }); await load(); onChanged(); } catch (e) { setError(e.message); } }
  return h('div', null,
    h(ErrorBox, { error }),
    h('div', { className: 'card' },
      h('h2', { className: 'text-lg font-bold' }, 'R4 purchase recommendation'),
      h('p', { className: 'mt-1 text-sm text-slate-600' }, 'R4 consumes external I2/I3/D4 contracts plus R1–R3 procurement evidence.'),
      h('div', { className: 'mt-4 flex flex-col gap-2 sm:flex-row' },
        h('input', { className: 'input max-w-xs', value: product, onChange: e => setProduct(e.target.value), 'aria-label': 'Product ID' }),
        h('button', { className: 'btn-primary', onClick: generate, disabled: busy }, busy ? 'Running R1–R4…' : 'Generate recommendation')
      )
    ),
    h('div', { className: 'mt-5 space-y-4' }, ...rows.slice(0, 25).map(r =>
      h('article', { key: r.recommendation_id, className: 'card' },
        h('div', { className: 'flex flex-wrap items-start justify-between gap-3' },
          h('div', null, h('p', { className: 'text-xs font-bold uppercase tracking-wide text-slate-500' }, `${r.agent_id} · ${r.action_type}`), h('h3', { className: 'mt-1 font-bold' }, r.entity_id), h('p', { className: 'mt-1 text-xs text-slate-500' }, r.recommendation_id)),
          h('div', { className: 'flex gap-2' }, h(Badge, { value: r.risk_level }), h(Badge, { value: r.status }))
        ),
        r.action?.supplier_id ? h('div', { className: 'mt-4 grid gap-3 sm:grid-cols-4 text-sm' },
          h('div', null, 'Supplier', h('strong', { className: 'block' }, r.action.supplier_id)),
          h('div', null, 'Quantity', h('strong', { className: 'block' }, r.action.qty ?? '—')),
          h('div', null, 'Expected cost', h('strong', { className: 'block' }, money(r.action.expected_cost))),
          h('div', null, 'Confidence', h('strong', { className: 'block' }, pct(r.confidence))),
        ) : null,
        h('ul', { className: 'mt-4 list-disc space-y-1 pl-5 text-sm text-slate-600' }, ...(r.rationale || []).map((x, i) => h('li', { key: i }, x))),
        r.status === 'READY_FOR_REVIEW' ? h('div', { className: 'mt-4 flex flex-wrap gap-2' },
          h('button', { className: 'btn-primary', onClick: () => decide(r.recommendation_id, 'APPROVED') }, 'Approve'),
          h('button', { className: 'btn-danger', onClick: () => decide(r.recommendation_id, 'REJECTED') }, 'Reject')
        ) : null,
        (r.agent_id === 'R4' && ['APPROVED', 'MODIFIED'].includes(r.status)) ? h('button', { className: 'btn-primary mt-4', onClick: () => execute(r.recommendation_id) }, 'Create purchase order') : null
      )
    ))
  );
}

function Orders({ refreshKey, onChanged }) {
  const [rows, setRows] = useState([]); const [result, setResult] = useState(null); const [error, setError] = useState('');
  const load = useCallback(() => api('/data/purchase_orders').then(setRows).catch(e => setError(e.message)), []);
  useEffect(() => { load(); }, [load, refreshKey]);
  async function reconcile(po) { setError(''); try { const r = await api(`/procurement/reconcile/${po}`, { method: 'POST' }); setResult(r); onChanged(); } catch (e) { setError(e.message); } }
  async function acceptAndClose() {
    if (!result) return;
    try {
      // An R5 result is evidence. When it found exceptions, the backend raised a
      // separate ReconciliationReview action; that is what the manager approves.
      if (result.action_recommendation_id) {
        await api(`/recommendations/${result.action_recommendation_id}/decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: 'APPROVED', reason: 'Procurement manager accepted reconciliation exceptions' }) });
      }
      await api(`/procurement/close/${result.entity_id}/${result.output_id || result.recommendation_id}`, { method: 'POST' });
      setResult(null); await load(); onChanged();
    } catch (e) { setError(e.message); }
  }
  return h('div', null,
    h(ErrorBox, { error }),
    h('div', { className: 'card overflow-x-auto' },
      h('h2', { className: 'text-lg font-bold' }, 'Purchase orders & R5 reconciliation'),
      h('p', { className: 'mb-4 mt-1 text-sm text-slate-600' }, 'R5 checks approved order, goods receipt and invoice evidence before closure.'),
      h('table', { className: 'w-full min-w-[800px]' },
        h('thead', { className: 'border-b text-left text-xs uppercase text-slate-500' }, h('tr', null, ...['PO', 'Supplier', 'Product', 'Qty', 'Value', 'Status', 'Action'].map(x => h('th', { key: x, className: 'table-cell' }, x)))),
        h('tbody', null, ...rows.map(po => h('tr', { key: po.po_id, className: 'border-b last:border-0' },
          h('td', { className: 'table-cell font-semibold' }, po.po_id), h('td', { className: 'table-cell' }, po.supplier_id), h('td', { className: 'table-cell' }, po.product_id), h('td', { className: 'table-cell' }, po.qty), h('td', { className: 'table-cell' }, money(po.qty * po.unit_cost)), h('td', { className: 'table-cell' }, h(Badge, { value: po.status })), h('td', { className: 'table-cell' }, h('button', { className: 'btn-secondary', onClick: () => reconcile(po.po_id), disabled: po.status === 'CLOSED' }, 'Run R5'))
        )))
      )
    ),
    result ? h('div', { className: 'card mt-5' },
      h('div', { className: 'flex items-center justify-between' }, h('h3', { className: 'font-bold' }, `R5 result · ${result.entity_id}`), h(Badge, { value: result.action.match_status })),
      h('p', { className: 'mt-3 text-sm text-slate-600' }, result.action.exception_types?.length ? `Exceptions: ${result.action.exception_types.join(', ')}` : 'No reconciliation exceptions detected.'),
      h('p', { className: 'mt-2 text-sm' }, `Financial variance: ${money(result.action.financial_variance)}`),
      result.status !== 'DRAFT' ? h('button', { className: 'btn-primary mt-4', onClick: acceptAndClose }, result.action_recommendation_id ? 'Accept result & close PO' : 'Close PO') : null
    ) : null
  );
}

function DataImports({ onChanged }) {
  const collections = ['suppliers', 'supplier_quotes', 'supplier_performance', 'purchase_orders', 'goods_receipts', 'invoices', 'demand_forecasts', 'inventory_positions', 'reorder_needs', 'safety_stock_targets'];
  const [collection, setCollection] = useState('supplier_quotes'); const [file, setFile] = useState(null); const [result, setResult] = useState(null); const [error, setError] = useState('');
  async function submit(e) { e.preventDefault(); if (!file) return; setError(''); try { const r = await uploadCsv(collection, file); setResult(r); onChanged(); } catch (err) { setError(err.message); } }
  return h('div', { className: 'grid gap-5 lg:grid-cols-2' },
    h('form', { className: 'card', onSubmit: submit },
      h('h2', { className: 'text-lg font-bold' }, 'Information layer · CSV import'),
      h('p', { className: 'mt-1 text-sm text-slate-600' }, 'Rows are schema-validated; invalid or duplicate records are isolated with reasons.'),
      h(ErrorBox, { error }),
      h('label', { className: 'mt-4 block text-sm font-semibold' }, 'Dataset'),
      h('select', { className: 'input mt-1', value: collection, onChange: e => setCollection(e.target.value) }, ...collections.map(c => h('option', { key: c, value: c }, c))),
      h('label', { className: 'mt-4 block text-sm font-semibold' }, 'CSV file'),
      h('input', { className: 'input mt-1', type: 'file', accept: '.csv,text/csv', onChange: e => setFile(e.target.files?.[0] || null) }),
      h('button', { className: 'btn-primary mt-4', disabled: !file }, 'Import & validate')
    ),
    h('div', { className: 'card' },
      h('h2', { className: 'text-lg font-bold' }, 'Import result'),
      result ? h('div', { className: 'mt-4 space-y-2 text-sm' },
        h('p', null, `Collection: ${result.collection}`), h('p', null, `Imported: ${result.imported}`), h('p', null, `Rejected: ${result.rejected}`), h('p', null, `Batch duplicates: ${result.duplicate_ids}`),
        result.errors?.length ? h('pre', { className: 'mt-3 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100' }, JSON.stringify(result.errors, null, 2)) : h('p', { className: 'text-emerald-700' }, 'No validation errors.')
      ) : h('p', { className: 'mt-4 text-sm text-slate-500' }, 'No import has been run in this session.')
    )
  );
}

function Audit({ refreshKey }) {
  const [rows, setRows] = useState([]); const [error, setError] = useState('');
  useEffect(() => { api('/audit').then(setRows).catch(e => setError(e.message)); }, [refreshKey]);
  return h('div', { className: 'card overflow-x-auto' },
    h('h2', { className: 'text-lg font-bold' }, 'Governance audit trail'), h(ErrorBox, { error }),
    h('table', { className: 'mt-4 w-full min-w-[760px]' },
      h('thead', { className: 'border-b text-left text-xs uppercase text-slate-500' }, h('tr', null, ...['Time', 'Event', 'Entity', 'Actor'].map(x => h('th', { key: x, className: 'table-cell' }, x)))),
      h('tbody', null, ...rows.slice(0, 100).map(r => h('tr', { key: r.event_id, className: 'border-b last:border-0' },
        h('td', { className: 'table-cell text-xs' }, String(r.created_at).replace('T', ' ').slice(0, 19)), h('td', { className: 'table-cell font-medium' }, r.event_type), h('td', { className: 'table-cell' }, `${r.entity_type}:${r.entity_id}`), h('td', { className: 'table-cell text-xs' }, r.actor_id)
      )))
    )
  );
}

export default function App() {
  const [page, setPage] = useState('Dashboard'); const [refreshKey, setRefreshKey] = useState(0); const [authReady, setAuthReady] = useState(import.meta.env.VITE_AUTH_MODE !== 'firebase'); const [user, setUser] = useState(import.meta.env.VITE_AUTH_MODE !== 'firebase' ? { email: 'manager@example.com' } : null);
  const changed = () => setRefreshKey(x => x + 1);
  useEffect(() => {
    if (import.meta.env.VITE_AUTH_MODE !== 'firebase') return undefined;
    let unsubscribe;
    getFirebaseAuth().then(async auth => {
      const { onAuthStateChanged } = await import('firebase/auth');
      unsubscribe = onAuthStateChanged(auth, u => { setUser(u); setAuthReady(true); });
    });
    return () => unsubscribe?.();
  }, []);
  const pages = useMemo(() => ['Dashboard', 'Suppliers', 'Recommendations', 'Purchase Orders', 'Data Imports', 'Audit'], []);
  if (!authReady) return h('div', { className: 'min-h-screen grid place-items-center' }, 'Checking authentication…');
  if (!user) return h(Login);
  const content = page === 'Dashboard' ? h(Dashboard, { refreshKey }) : page === 'Suppliers' ? h(Suppliers, { refreshKey }) : page === 'Recommendations' ? h(Recommendations, { refreshKey, onChanged: changed }) : page === 'Purchase Orders' ? h(Orders, { refreshKey, onChanged: changed }) : page === 'Data Imports' ? h(DataImports, { onChanged: changed }) : h(Audit, { refreshKey });
  async function signOut() { if (import.meta.env.VITE_AUTH_MODE === 'firebase') { const auth = await getFirebaseAuth(); const mod = await import('firebase/auth'); await mod.signOut(auth); } }
  return h('div', { className: 'min-h-screen' },
    h('header', { className: 'border-b border-slate-800 bg-slate-950 text-white' },
      h('div', { className: 'mx-auto flex max-w-[1500px] flex-col gap-4 px-5 py-5 lg:flex-row lg:items-center lg:justify-between' },
        h('div', null, h('p', { className: 'text-xs font-bold uppercase tracking-[0.18em] text-sky-300' }, 'Agent 4 · Procurement R1–R5'), h('h1', { className: 'mt-1 text-2xl font-bold' }, 'Retail Procurement Intelligence'), h('p', { className: 'mt-1 text-sm text-slate-400' }, 'Human-in-the-loop · Lightweight coordination · SMME-ready')),
        h('div', { className: 'flex items-center gap-3 text-sm' }, h('span', { className: 'text-slate-300' }, user.email), import.meta.env.VITE_AUTH_MODE === 'firebase' ? h('button', { className: 'btn-secondary', onClick: signOut }, 'Sign out') : h(Badge, { value: 'DEMO AUTH' }))
      )
    ),
    h('div', { className: 'mx-auto grid max-w-[1500px] gap-6 px-5 py-6 lg:grid-cols-[220px_1fr]' },
      h('nav', { className: 'card h-fit p-2' }, ...pages.map(name => h('button', { key: name, className: `w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold ${page === name ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`, onClick: () => setPage(name) }, name))),
      h('main', null, h('div', { className: 'mb-5 flex items-end justify-between gap-3' }, h('div', null, h('p', { className: 'text-xs font-semibold uppercase tracking-wide text-slate-500' }, 'Procurement workspace'), h('h2', { className: 'text-2xl font-bold' }, page)), h('button', { className: 'btn-secondary', onClick: changed }, 'Refresh')), content)
    )
  );
}
