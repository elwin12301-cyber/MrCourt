import { ClientCaseCard } from '../components/ClientCaseCard';
import { useClientDashboard } from '../services/client';

/** "My cases": every case the client has been invited to, open ones first. */
export default function ClientCases() {
  const { data, isLoading, isError } = useClientDashboard();
  const open = data?.cases.filter((c) => c.status !== 'closed') ?? [];
  const closed = data?.cases.filter((c) => c.status === 'closed') ?? [];

  return (
    <section className="view" id="cases" data-view="client-cases">
      <div>
        <h1>My cases</h1>
        <p className="sub">
          {data ? `${open.length} open · ${closed.length} closed` : ''}
        </p>
      </div>
      {isError && (
        <p className="sub" role="alert">
          We could not load your cases. Please try again.
        </p>
      )}
      {!isLoading && !isError && data?.cases.length === 0 && (
        <p className="sub">
          You have no cases yet. Your lawyer will invite you, and the case will appear here.
        </p>
      )}
      <div className="stack">
        {open.map((c) => <ClientCaseCard key={c.id} item={c} />)}
        {closed.length > 0 && <h2 style={{ marginTop: 8 }}>Closed</h2>}
        {closed.map((c) => <ClientCaseCard key={c.id} item={c} />)}
      </div>
    </section>
  );
}
