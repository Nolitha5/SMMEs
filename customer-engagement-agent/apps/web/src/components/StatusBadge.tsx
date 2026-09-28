export function StatusBadge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'blue' }) {
  const map = { neutral:'border-slate-700 bg-slate-800/70 text-slate-300', good:'border-emerald-800 bg-emerald-950/60 text-emerald-300', warn:'border-amber-800 bg-amber-950/60 text-amber-300', bad:'border-rose-800 bg-rose-950/60 text-rose-300', blue:'border-blue-800 bg-blue-950/60 text-blue-300' };
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${map[tone]}`}>{children}</span>;
}
