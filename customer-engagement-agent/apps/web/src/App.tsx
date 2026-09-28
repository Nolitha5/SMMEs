import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { useBootstrap } from './hooks/useBootstrap';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import AgentLab from './pages/AgentLab';
import FeedbackPage from './pages/Feedback';
import Integrations from './pages/Integrations';
import SyncPage from './pages/Sync';

export default function App(){const ready=useBootstrap(); if(!ready)return <div className="grid min-h-screen place-items-center bg-slate-950 text-sm text-slate-500">Preparing offline workspace…</div>; return <Routes><Route element={<Layout/>}><Route index element={<Dashboard/>}/><Route path="customers" element={<Customers/>}/><Route path="agent-lab" element={<AgentLab/>}/><Route path="feedback" element={<FeedbackPage/>}/><Route path="integrations" element={<Integrations/>}/><Route path="sync" element={<SyncPage/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Route></Routes>}
