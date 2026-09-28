import { Activity, AlertTriangle, DatabaseZap, MessageSquareText, Play, UsersRound } from 'lucide-react';
import { useLiveQuery } from 'dexie-react-hooks';
import { DEMO_BUSINESS_ID, type Insight } from '@cea/shared';
import { AgentCard } from '../components/AgentCard';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { db } from '../lib/db';
import { runAndPersistBusinessCycle } from '../lib/repository';
import { useState } from 'react';

const agents = [
  ['C1','Customer Segmentation','Groups customers using recency, frequency and spend.','Sales + customer profile','segment insight + event'],
  ['C2','Retention Risk','Turns recency and feedback signals into an explainable churn score.','C1 + C5','risk insight + event'],
  ['C3','Promotion Recommender','Chooses offers with consent, stock and margin guardrails.','C1 + Sales + Inventory + Pricing','promotion recommendation'],
  ['C4','Next-Best-Action','Coordinates all prior outputs into one human-reviewable action.','C1 + C2 + C3 + C5','next action + event'],
  ['C5','Feedback & Sentiment','Extracts sentiment, topics and urgency using offline rules.','Feedback','sentiment insight + event']
] as const;

export default function Dashboard() {
  const customers = useLiveQuery(() => db.customers.count(), []) ?? 0;
  const insights = useLiveQuery(() => db.insights.toArray(), []) ?? [];
  const feedback = useLiveQuery(() => db.feedback.count(), []) ?? 0;
  const queued = useLiveQuery(() => db.syncQueue.count(), []) ?? 0;
  const [running,setRunning]=useState(false);
  const highRisk = insights.filter((i: Insight) => i.agentId === 'C2' && i.score >= 60).length;
  const latestActions = insights.filter((i: Insight) => i.agentId === 'C4').slice(-4).reverse();

  const run = async () => { setRunning(true); try { await runAndPersistBusinessCycle(import.meta.env.VITE_BUSINESS_ID || DEMO_BUSINESS_ID); } finally { setRunning(false); } };
  return <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
    <PageHeader eyebrow="Customer Engagement Agent" title="Engagement command centre" description="C1–C5 are one headless-ready agent core. This standalone screen is only a test harness; the final platform will supply the shared interface, authentication and Firebase connection." action={<button className="btn-primary" onClick={run} disabled={running}><Play className="size-4"/>{running ? 'Running…' : 'Run C1–C5 cycle'}</button>} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Customers" value={customers} helper="Shared customer records available locally." icon={UsersRound}/>
      <MetricCard label="Feedback items" value={feedback} helper="C5 can analyse these without internet." icon={MessageSquareText}/>
      <MetricCard label="High-risk signals" value={highRisk} helper="C2 insights with a score of 60 or higher." icon={AlertTriangle}/>
      <MetricCard label="Queued cloud writes" value={queued} helper="Local-first changes waiting for Firebase sync." icon={DatabaseZap}/>
    </div>

    <section className="mt-7"><div className="mb-3 flex items-center justify-between"><div><h2 className="text-sm font-semibold text-white">Internal capabilities</h2><p className="mt-1 text-xs text-slate-500">One agent. Five coordinated functions.</p></div><StatusBadge tone="blue">Dependency-aware orchestration</StatusBadge></div><div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">{agents.map(([id,name,role,reads,writes]) => <AgentCard key={id} id={id} name={name} role={role} reads={reads} writes={writes}/>)}</div></section>

    <section className="mt-7 grid gap-4 xl:grid-cols-[1.35fr_.65fr]">
      <div className="card p-5"><div className="flex items-center gap-2"><Activity className="size-4 text-blue-400"/><h2 className="text-sm font-semibold text-white">Latest next-best actions</h2></div><div className="mt-4 space-y-2">{latestActions.length ? latestActions.map(i => { const p=i.payload as any; return <div key={i.id} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3"><div className="flex items-center justify-between gap-3"><p className="text-xs font-medium text-slate-200">{p.summary}</p><StatusBadge tone={p.priority === 'high' ? 'bad' : p.priority === 'medium' ? 'warn' : 'neutral'}>{p.priority}</StatusBadge></div><p className="mt-2 text-[11px] text-slate-600">Customer · {i.customerId}</p></div>}) : <div className="rounded-2xl border border-dashed border-slate-800 p-7 text-center text-xs text-slate-500">Run the C1–C5 cycle to create coordinated recommendations.</div>}</div></div>
      <div className="card p-5"><h2 className="text-sm font-semibold text-white">Shared-agent boundary</h2><p className="mt-3 text-xs leading-6 text-slate-400">Customer Engagement reads authoritative Sales, Inventory and Pricing data. It publishes insights and events back to the shared Firebase namespace, but does not directly change stock or prices.</p><div className="mt-4 rounded-2xl bg-blue-600/10 p-3 text-[11px] leading-5 text-blue-200">Offline writes land in IndexedDB first, so a dropped connection does not stop core C1–C5 analysis.</div></div>
    </section>
  </div>;
}
