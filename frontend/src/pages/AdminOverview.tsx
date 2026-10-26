import { Link } from 'react-router-dom';
import { AuditList } from '../components/AuditList';
import { VoicePanel } from '../components/VoicePanel';
import { useOverview } from '../services/admin';
import { formatToday } from './Dashboard';

function Stat({ to, value, label }: { to: string; value: number | undefined; label: string }) {
  return (
    <Link to={to} className="card stat statlink">
      <b>{value ?? '–'}</b>
      <span>{label}</span>
    </Link>
  );
}

/** What an administrator sees first: how big the system is, what needs attention, what was done lately. */
export default function AdminOverview() {
  const { data, isError } = useOverview();
  return (
    <section className="view" id="admin-overview" data-view="admin-overview">
      <div>
        <h1>Administration</h1>
        <p className="sub">{formatToday(new Date())}</p>
      </div>
      <VoicePanel />
      {isError && (
        <p className="sub" role="alert">
          We could not load the overview. Please try again.
        </p>
      )}
      <div className="row">
        <Stat to="/admin/advocates" value={data?.advocates} label="Advocates" />
        <Stat to="/admin/clients" value={data?.clients} label="Clients" />
        <Stat to="/admin/cases" value={data?.open_cases} label="Open cases" />
      </div>
      <div className="row">
        <Stat to="/admin/verifications" value={data?.pending_verifications} label="Waiting for verification" />
        <Stat to="/admin/advocates" value={data?.suspended_accounts} label="Suspended accounts" />
      </div>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2>Latest activity</h2>
          <Link to="/admin/audit" className="back" aria-label="See the whole audit log" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
            Audit log
          </Link>
        </div>
        <AuditList items={data?.recent_audit ?? []} />
      </div>
    </section>
  );
}
