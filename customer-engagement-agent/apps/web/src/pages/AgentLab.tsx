import { useLiveQuery } from 'dexie-react-hooks';
import { BrainCircuit, Play } from 'lucide-react';
import { useMemo, useState } from 'react';
import { DEMO_BUSINESS_ID, runCustomerCycle } from '@cea/shared';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { db } from '../lib/db';
import { runAndPersistBusinessCycle } from '../lib/repository';

export default function AgentLab(){
  const customers=useLiveQuery(()=>db.customers.toArray(),[])??[];
  const transactions=useLiveQuery(()=>db.transactions.toArray(),[])??[];
  const products=useLiveQuery(()=>db.products.toArray(),[])??[];
  const feedback=useLiveQuery(()=>db.feedback.toArray(),[])??[];
  const [selected,setSelected]=useState('cus-sipho');
  const customer=customers.find(c=>c.id===selected)??customers[0];
  const result=useMemo(()=>customer?runCustomerCycle(customer,transactions,products,feedback):null,[customer,transactions,products,feedback]);
  const cards=result?[result.segment,result.churn,result.promotion,result.nextAction,result.feedback]:[];
  return <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8"><PageHeader eyebrow="Explainability workspace" title="Agent Lab" description="Inspect what each internal capability concludes for the same customer and how C4 composes the final action." action={<button className="btn-primary" onClick={()=>runAndPersistBusinessCycle(import.meta.env.VITE_BUSINESS_ID||DEMO_BUSINESS_ID)}><Play className="size-4"/>Persist full cycle</button>}/>
    <div className="card p-4"><label className="text-xs text-slate-500">Customer</label><select className="input mt-2" value={customer?.id||''} onChange={e=>setSelected(e.target.value)}>{customers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
    {result&&<div className="mt-4 grid gap-3 lg:grid-cols-2">{cards.map((piece:any)=><div key={piece.agentId} className="card p-4"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-xl bg-blue-600/15 text-xs font-bold text-blue-300">{piece.agentId}</div><p className="text-sm font-semibold text-white">{{C1:'Segmentation',C2:'Retention Risk',C3:'Promotion',C4:'Next-Best-Action',C5:'Feedback & Sentiment'}[piece.agentId as 'C1']}</p></div><StatusBadge tone="blue">local engine</StatusBadge></div><pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-950/70 p-3 text-[11px] leading-5 text-slate-400">{JSON.stringify(piece,null,2)}</pre></div>)}</div>}
    <div className="mt-4 card p-4"><div className="flex items-center gap-2"><BrainCircuit className="size-4 text-blue-400"/><p className="text-sm font-semibold text-white">Coordinator order</p></div><p className="mt-2 text-xs leading-6 text-slate-400">C1 → C5 → C2 → C3 → C4. C5 runs before C2 because recent negative feedback is a retention-risk signal; C4 runs last because it consumes the others.</p></div>
  </div>
}
