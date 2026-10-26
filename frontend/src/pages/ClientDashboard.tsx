import { Link } from 'react-router-dom';
import { ClientCaseCard } from '../components/ClientCaseCard';
import { LawyerCard } from '../components/LawyerCard';
import { VoicePanel } from '../components/VoicePanel';
import { useMe } from '../services/auth';
import { timeAgo } from '../services/cases';
import { useClientDashboard } from '../services/client';
import { formatToday, greetingFor, greetingName } from './Dashboard';

/** The dashboard a client sees: their own cases, where each stands, and what happens next. */
export default function ClientDashboard() {
  const { data: me } = useMe();
  const { data, isLoading, isError } = useClientDashboard();
  if (!me) return null;
  const now = new Date();
  // One card per lawyer, even when the same lawyer handles several of the client's cases.
  const lawyers = [...new Map((data?.cases ?? []).map((c) => [c.lawyer.name, c.lawyer])).values()];

  return (
    <section className="view" id="dashboard" data-view="client-dashboard">
      <div>
        <h1>
          {greetingFor(now)}, {greetingName(me.full_name)}
        </h1>
        <p className="sub">{formatToday(now)}</p>
      </div>

      <VoicePanel />

      <div className="stack">
        <h2>My cases</h2>
        {isError && (
          <p className="sub" role="alert">
            We could not load your cases. Please try again.
          </p>
        )}
        {!isLoading && !isError && data?.cases.length === 0 && (
          <div className="card">
            <h2 style={{ marginBottom: 8 }}>Your cases will appear here</h2>
            <p className="sub" style={{ margin: 0 }}>
              Your lawyer invites you to a case from their MrCourt account. Once you accept, you will
              see where it stands and what happens next. Ask your lawyer to send an invitation to the
              email or phone number you signed up with.
            </p>
          </div>
        )}
        {data?.cases.map((c) => <ClientCaseCard key={c.id} item={c} />)}
      </div>

      {data && data.latest_updates.length > 0 && (
        <div className="card" id="latest-updates">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <h2>
              Latest updates {data.unread_updates > 0 && <span className="badge">{data.unread_updates} unread</span>}
            </h2>
            <Link to="/updates" className="back" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
              See all
            </Link>
          </div>
          {data.latest_updates.map((u) => (
            <div className="act" key={u.id}>
              <span className={u.read ? undefined : 'unread'} style={{ color: 'inherit', fontSize: 'inherit' }}>
                {!u.read && <span className="badge" style={{ marginRight: 8 }}>New</span>}
                {u.message}
              </span>
              <span>{timeAgo(u.created_at)}</span>
            </div>
          ))}
        </div>
      )}

      {data && data.cases.length > 0 && (
        <div className="stack">
          {lawyers.map((lawyer) => <LawyerCard key={lawyer.name} lawyer={lawyer} />)}
        </div>
      )}
    </section>
  );
}
