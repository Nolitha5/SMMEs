import { NavLink, Outlet } from 'react-router-dom';
import { Activity, Boxes, CloudCog, DatabaseZap, LayoutDashboard, MessageSquareText, UsersRound, Wifi, WifiOff } from 'lucide-react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../lib/db';
import { useOnline } from '../hooks/useOnline';
import { firebaseEnabled } from '../lib/firebase';

const items = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/customers', label: 'Customers', icon: UsersRound },
  { to: '/agent-lab', label: 'Agent Lab', icon: Activity },
  { to: '/feedback', label: 'Feedback', icon: MessageSquareText },
  { to: '/integrations', label: 'Integrations', icon: Boxes },
  { to: '/sync', label: 'Sync', icon: DatabaseZap }
];

export default function Layout() {
  const online = useOnline();
  const queued = useLiveQuery(() => db.syncQueue.count(), []) ?? 0;
  return <div className="min-h-screen lg:grid lg:grid-cols-[238px_1fr]">
    <aside className="border-b border-slate-800/80 bg-slate-950/70 px-4 py-4 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:px-4 lg:py-5">
      <div className="flex items-center justify-between lg:block">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-10 place-items-center rounded-2xl bg-blue-600 shadow-lg shadow-blue-900/30"><MessageSquareText className="size-5" /></div>
          <div><p className="text-sm font-semibold text-white">Customer Engagement</p><p className="text-[11px] text-slate-500">One agent · C1–C5</p></div>
        </div>
        <div className="flex items-center gap-2 lg:mt-6 lg:px-2">
          <span className="pill flex items-center gap-1.5">{online ? <Wifi className="size-3.5 text-emerald-400"/> : <WifiOff className="size-3.5 text-amber-400"/>}{online ? 'Online' : 'Offline'}</span>
        </div>
      </div>
      <nav className="mt-4 grid grid-cols-3 gap-2 lg:mt-7 lg:grid-cols-1">
        {items.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} end={to === '/'} className={({isActive}) => `flex items-center gap-2 rounded-2xl px-3 py-2.5 text-xs font-medium transition lg:text-sm ${isActive ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'}`}><Icon className="size-4"/><span className="truncate">{label}</span></NavLink>)}
      </nav>
      <div className="mt-5 hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-3 lg:block">
        <div className="flex items-center gap-2 text-xs text-slate-300"><CloudCog className="size-4 text-blue-400" />{firebaseEnabled ? 'Shared Firebase configured' : 'Standalone test harness'}</div>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">{queued} change{queued === 1 ? '' : 's'} waiting in the offline sync queue.</p>
      </div>
    </aside>
    <main className="min-w-0"><Outlet /></main>
  </div>;
}
