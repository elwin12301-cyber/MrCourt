import { Link } from 'react-router-dom';
import { timeAgo } from '../services/cases';
import { useClientUpdates, useMarkUpdatesRead } from '../services/client';
import { Button } from '../components/ui';

/** Everything the lawyer has changed on the client's cases, newest first, with what is still unread. */
export default function Updates() {
  const { data, isLoading, isError } = useClientUpdates(true);
  const mark = useMarkUpdatesRead();
  const unread = data?.unread_count ?? 0;

  return (
    <section className="view" id="updates" data-view="updates">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <h1>Updates</h1>
          <p className="sub" aria-live="polite">
            {unread > 0 ? `${unread} unread` : 'You are up to date'}
          </p>
        </div>
        <Button small variant="ghost" disabled={unread === 0 || mark.all.isPending} onClick={() => mark.all.mutate()}>
          Mark all as read
        </Button>
      </div>

      {isError && <p className="sub" role="alert">We could not load your updates. Please try again.</p>}
      {!isLoading && !isError && data?.items.length === 0 && (
        <p className="sub">
          Nothing yet. When your lawyer changes a status, schedules a hearing or shares something, you will see it here.
        </p>
      )}

      <div className="card" style={{ padding: '8px 22px' }}>
        {data?.items.map((u) => (
          <Link
            key={u.id}
            to={`/cases/${u.case_id}`}
            className="act updaterow"
            onClick={() => {
              if (!u.read) mark.one.mutate(u.id);
            }}
          >
            <span className={u.read ? undefined : 'unread'}>
              {!u.read && <span className="badge" style={{ marginRight: 8 }}>New</span>}
              {u.message}
            </span>
            <span>{timeAgo(u.created_at)}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
