import type { LucideIcon } from 'lucide-react';
export function MetricCard({ label, value, helper, icon: Icon }: { label: string; value: string | number; helper: string; icon: LucideIcon }) {
  return <div className="card p-4"><div className="flex items-start justify-between"><div><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-white">{value}</p></div><div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-2.5"><Icon className="size-4 text-blue-400" /></div></div><p className="mt-3 text-[11px] leading-5 text-slate-500">{helper}</p></div>;
}
