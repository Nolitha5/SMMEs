import { ArrowLeftRight, Database, PackageCheck, ReceiptText, ShieldCheck } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { firebaseEnabled } from '../lib/firebase';

const connections=[
  ['Sales Agent','transactions, baskets, recency','C1 C2 C3 C4','Read authoritative sales history',ReceiptText],
  ['Inventory Agent','stock, reorder level, active SKU','C3 C4','Read only; never decrement stock',PackageCheck],
  ['Pricing / Finance','margin %, campaign limits','C3','Read guardrails; emit recommendation',Database],
  ['Platform Coordinator','engagement events','C1–C5','Publish typed events for other agents',ArrowLeftRight]
] as const;
export default function Integrations(){return <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8"><PageHeader eyebrow="25-agent interoperability" title="Shared-agent integrations" description="This module is designed for one shared Firebase project and one business namespace. Other top-level agents can consume engagement outputs without coupling to C1–C5 internals."/>
  <div className="card p-5"><div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">Firebase mode</p><p className="mt-1 text-xs text-slate-500">businesses/{'{businessId}'}/…</p></div><StatusBadge tone={firebaseEnabled?'good':'warn'}>{firebaseEnabled?'Enabled':'Standalone harness'}</StatusBadge></div><div className="mt-4 rounded-2xl bg-slate-950/60 p-3 text-xs leading-6 text-slate-400">Collections: <span className="text-slate-200">customers · transactions · products · feedback · insights · events · syncAudit</span></div></div>
  <div className="mt-4 grid gap-3 lg:grid-cols-2">{connections.map(([name,data,uses,boundary,Icon])=><div key={name} className="card p-4"><div className="flex items-center gap-3"><div className="rounded-2xl bg-blue-600/15 p-2.5"><Icon className="size-4 text-blue-400"/></div><div><h3 className="text-sm font-semibold text-white">{name}</h3><p className="text-[11px] text-slate-500">Used by {uses}</p></div></div><p className="mt-4 text-xs text-slate-400">{data}</p><p className="mt-2 text-[11px] text-slate-600">Boundary · {boundary}</p></div>)}</div>
  <div className="mt-4 card p-5"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-emerald-400"/><h2 className="text-sm font-semibold text-white">Security contract</h2></div><p className="mt-3 text-xs leading-6 text-slate-400">Included Firestore rules require authentication plus a business membership document. Writes must carry the same businessId as the path. Owner/manager roles control membership changes.</p></div>
</div>}
