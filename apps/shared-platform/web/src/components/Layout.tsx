import {
  Activity,
  BadgeDollarSign,
  Boxes,
  ChartNoAxesCombined,
  ClipboardCheck,
  LayoutDashboard,
  Menu,
  PackageSearch,
  UsersRound,
  X,
  Gauge,
  Database,
  Play
} from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { useState } from 'react';
import { signOut } from 'firebase/auth';
import { authMode, clientAuth } from '../lib/firebase';
import { useWorkspace } from '../context';

const nav = [
  ['/', 'Overview', LayoutDashboard],
  ['/approvals', 'Approvals', ClipboardCheck],
  ['/activity', 'Activity', Activity],
  ['/data', 'Business data', Database],
  ['/process', 'Process data', Play],
  ['/domain/demand', 'Demand', ChartNoAxesCombined],
  ['/domain/inventory', 'Inventory', Boxes],
  ['/domain/pricing', 'Pricing', BadgeDollarSign],
  ['/domain/procurement', 'Procurement', PackageSearch],
  ['/domain/customer-engagement', 'Customers', UsersRound],
  ['/system', 'System', Gauge]
] as const;

export function Layout() {
  const [open, setOpen] = useState(false);
  const { data } = useWorkspace();

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-wordmark">
            <strong>SME Operations</strong>
            <span>Business workspace</span>
          </div>
          <button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>

        <nav>
          {nav.map(([to, label, Icon]) => (
            <NavLink
              end={to === '/'}
              key={to}
              to={to}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setOpen(false)}
            >
              <Icon size={17} strokeWidth={1.9} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className="dot" />
          <div>
            <strong>{data?.connected ? 'Connected' : 'Connection unavailable'}</strong>
            <span>{data?.connected ? 'Workspace online' : 'Check workspace connection'}</span>
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-only" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu size={19} />
          </button>
          <div className="topbar-title">
            <span className="eyebrow">Operations workspace</span>
          </div>
          {authMode === 'firebase' && clientAuth()?.currentUser ? (
            <button className="text-button topbar-signout" onClick={() => void signOut(clientAuth()!)}>
              Sign out
            </button>
          ) : null}
        </header>
        <main className="workspace">
          <Outlet />
        </main>
      </div>

      {open ? <button className="scrim mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation overlay" /> : null}
    </div>
  );
}
