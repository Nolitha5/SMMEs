import { useLiveQuery } from 'dexie-react-hooks';
import { MessageSquarePlus } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { DEMO_BUSINESS_ID } from '@cea/shared';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { db } from '../lib/db';
import { addFeedback } from '../lib/repository';

export default function FeedbackPage(){
  const customers=useLiveQuery(()=>db.customers.toArray(),[])??[]; const feedback=useLiveQuery(()=>db.feedback.orderBy('createdAt').reverse().toArray(),[])??[];
  const [customerId,setCustomerId]=useState('cus-sipho'); const [message,setMessage]=useState(''); const [channel,setChannel]=useState<'in-store'|'whatsapp'|'sms'|'web'|'other'>('in-store');
  const submit=async(e:FormEvent)=>{e.preventDefault(); if(!message.trim())return; await addFeedback({businessId:import.meta.env.VITE_BUSINESS_ID||DEMO_BUSINESS_ID,customerId,channel,message:message.trim()}); setMessage('');};
  return <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8"><PageHeader eyebrow="C5 input" title="Feedback inbox" description="Feedback is captured locally first. C5 can analyse sentiment, topics and urgency even without internet."/>
    <div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]"><form className="card p-5" onSubmit={submit}><div className="flex items-center gap-2"><MessageSquarePlus className="size-4 text-blue-400"/><h2 className="text-sm font-semibold text-white">Add feedback</h2></div><label className="mt-4 block text-xs text-slate-500">Customer</label><select className="input mt-2" value={customerId} onChange={e=>setCustomerId(e.target.value)}>{customers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select><label className="mt-4 block text-xs text-slate-500">Channel</label><select className="input mt-2" value={channel} onChange={e=>setChannel(e.target.value as any)}><option value="in-store">In-store</option><option value="whatsapp">WhatsApp</option><option value="sms">SMS</option><option value="web">Web</option><option value="other">Other</option></select><label className="mt-4 block text-xs text-slate-500">Message</label><textarea className="input mt-2 min-h-32 resize-y" placeholder="Customer said…" value={message} onChange={e=>setMessage(e.target.value)}/><button className="btn-primary mt-4 w-full">Save offline-first</button></form>
      <div className="card p-5"><h2 className="text-sm font-semibold text-white">Recent feedback</h2><div className="mt-4 space-y-2">{feedback.map(f=><div key={f.id} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3"><div className="flex items-center justify-between gap-3"><p className="text-[11px] text-slate-500">{customers.find(c=>c.id===f.customerId)?.name||f.customerId}</p><StatusBadge>{f.channel}</StatusBadge></div><p className="mt-2 text-xs leading-5 text-slate-300">{f.message}</p></div>)}</div></div></div>
  </div>
}
