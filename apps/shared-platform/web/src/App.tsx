import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthGate } from './components/AuthGate';
import { WorkspaceProvider } from './context';
import { ActivityPage } from './pages/Activity';
import { Approvals } from './pages/Approvals';
import { DomainPage } from './pages/Domain';
import { Login } from './pages/Login';
import { Overview } from './pages/Overview';
import { SystemPage } from './pages/System';
import { DataPage } from './pages/Data';
import { ProcessPage } from './pages/Process';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <AuthGate>
              <WorkspaceProvider>
                <Layout />
              </WorkspaceProvider>
            </AuthGate>
          }
        >
          <Route index element={<Overview />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/process" element={<ProcessPage />} />
          <Route path="/domain/:domain" element={<DomainPage />} />
          <Route path="/system" element={<SystemPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
