import { useLiveQuery } from 'dexie-react-hooks';
import { Search, ShieldCheck, ShieldX } from 'lucide-react';
import { useMemo, useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { db } from '../lib/db';

export default function Customers() {
  const customers = useLiveQuery(() => db.customers.toArray(), []) ?? [];
  const insights = useLiveQuery(() => db.insights.toArray(), []) ?? [];
  const [q,setQ]=useState('');
  const rows=useMemo(()=>customers.filter(c=>c.name.toLowerCase().includes(q.toLowerCase())),[customers,q]);
  const latest=(customerId:string,agentId:string)=>insights.find(i=>i.customerId===customerId&&i.agentId===agentId);
  return <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8"><PageHeader eyebrow="Shared customer data" title="Customers" description="Customer records are shared inputs. Engagement insights remain explainable and marketing consent is enforced before C3 proposes an offer." />
    <div className="card p-3"><div className="relative"><Search className="absolute left-4 top-3.5 size-4 text-slate-600"/><input className="input pl-10" placeholder="Search customers" value={q} onChange={e=>setQ(e.target.value)}/></div></div>
    <div className="mt-4 grid gap-3 lg:grid-cols-2">{rows.map(c=>{const seg:any=latest(c.id,'C1')?.payload; const risk:any=latest(c.id,'C2')?.payload; const action:any=latest(c.id,'C4')?.payload; return <div className="card p-4" key={c.id}><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">{c.name}</h3><p className="mt-1 text-[11px] text-slate-500">{c.phone || 'No phone stored'} · {c.tags.join(', ') || 'No tags'}</p></div>{c.consentMarketing?<StatusBadge tone="good"><ShieldCheck className="mr-1 size-3"/>Consent</StatusBadge>:<StatusBadge tone="neutral"><ShieldX className="mr-1 size-3"/>No marketing</StatusBadge>}</div><div className="mt-4 flex flex-wrap gap-2"><StatusBadge tone="blue">{seg?.segment || 'Not segmented'}</StatusBadge><StatusBadge tone={risk?.riskBand==='high'||risk?.riskBand==='critical'?'bad':risk?.riskBand==='medium'?'warn':'good'}>{risk?`${risk.riskBand} risk · ${risk.riskScore}`:'No risk score'}</StatusBadge></div><p className="mt-4 rounded-2xl bg-slate-950/60 p-3 text-xs leading-5 text-slate-400">{action?.summary || 'Run C1–C5 to generate a next-best action.'}</p></div>})}</div>
  </div>;
}
