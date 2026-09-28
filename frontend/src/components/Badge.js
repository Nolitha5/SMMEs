import React from 'react';
const h = React.createElement;

export default function Badge({ value }) {
  const text = String(value || '—');
  const upper = text.toUpperCase();
  const tone = upper.includes('HIGH') || upper.includes('REJECT') || upper.includes('MISMATCH')
    ? 'bg-red-100 text-red-700'
    : upper.includes('MEDIUM') || upper.includes('REVIEW') || upper.includes('PARTIAL')
      ? 'bg-amber-100 text-amber-800'
      : upper.includes('LOW') || upper.includes('APPROVED') || upper.includes('MATCH') || upper.includes('EXECUTED') || upper.includes('CLOSED')
        ? 'bg-emerald-100 text-emerald-700'
        : 'bg-slate-100 text-slate-700';
  return h('span', { className: `inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}` }, text);
}
