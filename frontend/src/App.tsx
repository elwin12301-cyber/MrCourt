import type { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { IconSprite } from './components/Icon';
import AdminAudit from './pages/AdminAudit';
import AdminMessages from './pages/AdminMessages';
import AdminCaseView from './pages/AdminCaseView';
import AdminCases from './pages/AdminCases';
import AdminOverview from './pages/AdminOverview';
import AdminUserDetail from './pages/AdminUserDetail';
import AdminUsers from './pages/AdminUsers';
import AdminVerifications from './pages/AdminVerifications';
import Ask from './pages/Ask';
import DevMessages from './pages/DevMessages';
import ForgotPassword from './pages/ForgotPassword';
import CaseDetail from './pages/CaseDetail';
import Cases from './pages/Cases';
import ClientCaseDetail from './pages/ClientCaseDetail';
import ClientCases from './pages/ClientCases';
import ClientDashboard from './pages/ClientDashboard';
import Dashboard from './pages/Dashboard';
import Drafts from './pages/Drafts';
import Login, { LoginRedirect } from './pages/Login';
import Register from './pages/Register';
import Settings from './pages/Settings';
import Updates from './pages/Updates';
import Welcome from './pages/Welcome';
import { useMe } from './services/auth';
import { VoiceProvider } from './voice/VoiceProvider';

/**
 * Picks the screen for the signed-in person's role: clients get their own, advocates keep theirs,
 * administrators get the admin area (or are sent to their overview where there is no admin version).
 */
function ByRole({ advocate, client, admin }: { advocate: JSX.Element; client: JSX.Element; admin?: JSX.Element }) {
  const { data: me } = useMe();
  if (!me) return null;
  if (me.role === 'admin') return admin ?? <Navigate to="/dashboard" replace />;
  return me.role === 'petitioner' ? client : advocate;
}

/** For screens that exist for advocates and clients but not administrators. */
function NotAdmin({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  if (!me) return null;
  return me.role === 'admin' ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}

/** Administrator-only screens. Anyone else is told so; the server refuses them as well. */
function AdminOnly({ children }: { children: ReactNode }) {
  const { data: me } = useMe();
  if (!me) return null;
  if (me.role !== 'admin') {
    return (
      <section className="view">
        <h1>Administration</h1>
        <p className="sub">This page is for administrators only.</p>
      </section>
    );
  }
  return <>{children}</>;
}

/** Sends signed-out visitors to the welcome screen and remembers where they were going. */
export function RequireAuth() {
  const { data: me, isLoading } = useMe();
  const location = useLocation();
  if (isLoading) return null;
  if (!me) return <Navigate to="/" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export default function App() {
  return (
    <VoiceProvider>
      <IconSprite />
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/login" element={<LoginRedirect />} />
        <Route path="/login/:role" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/register/:role" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/dev/messages" element={<DevMessages />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route
              path="/dashboard"
              element={<ByRole advocate={<Dashboard />} client={<ClientDashboard />} admin={<AdminOverview />} />}
            />
            <Route path="/cases" element={<ByRole advocate={<Cases />} client={<ClientCases />} />} />
            <Route path="/cases/:caseId" element={<ByRole advocate={<CaseDetail />} client={<ClientCaseDetail />} />} />
            <Route path="/ask/*" element={<Ask />} />
            <Route path="/drafts" element={<NotAdmin><Drafts /></NotAdmin>} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/updates" element={<ByRole advocate={<Navigate to="/dashboard" replace />} client={<Updates />} />} />

            <Route path="/admin/advocates" element={<AdminOnly><AdminUsers kind="advocate" /></AdminOnly>} />
            <Route path="/admin/advocates/:userId" element={<AdminOnly><AdminUserDetail /></AdminOnly>} />
            <Route path="/admin/clients" element={<AdminOnly><AdminUsers kind="petitioner" /></AdminOnly>} />
            <Route path="/admin/clients/:userId" element={<AdminOnly><AdminUserDetail /></AdminOnly>} />
            <Route path="/admin/cases" element={<AdminOnly><AdminCases /></AdminOnly>} />
            <Route path="/admin/cases/:caseId" element={<AdminOnly><AdminCaseView /></AdminOnly>} />
            <Route path="/admin/verifications" element={<AdminOnly><AdminVerifications /></AdminOnly>} />
            <Route path="/admin/knowledge" element={<Navigate to="/ask/knowledge" replace />} />
            <Route path="/admin/messages" element={<AdminOnly><AdminMessages /></AdminOnly>} />
            <Route path="/admin/audit" element={<AdminOnly><AdminAudit /></AdminOnly>} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </VoiceProvider>
  );
}
