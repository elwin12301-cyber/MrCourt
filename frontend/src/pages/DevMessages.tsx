import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

interface DevMessage {
  to: string;
  kind: string;
  text: string;
  at: string;
}

/** Development only: the text messages that would have been sent (codes and reminders). */
export default function DevMessages() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['dev-messages'],
    queryFn: () => api.get<DevMessage[]>('/dev/messages'),
    refetchInterval: 3000,
    retry: false,
  });
  return (
    <main className="view" id="dev-messages" style={{ maxWidth: 820, margin: '0 auto', padding: '32px 16px' }}>
      <Link to="/" className="back">
        Back to MrCourt
      </Link>
      <h1>Development messages</h1>
      <p className="sub">
        Text messages are not really sent while no text-message service is set up. Here is what would have been sent. This
        page does not exist in production.
      </p>
      {isError && <p role="alert">Not available here: either a real text-message service is set up, or this is not a development setup.</p>}
      {!isError && !isLoading && data?.length === 0 && <p>No messages yet.</p>}
      <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }} aria-label="Messages">
        {data?.map((m, i) => (
          <li key={`${m.at}-${i}`} className="card">
            <div className="fine" style={{ margin: 0 }}>
              To {m.to} · {m.kind === 'reminder' ? 'Reminder' : 'Code'} · {new Date(m.at).toLocaleString('en-IN')}
            </div>
            <p style={{ margin: '6px 0 0' }}>{m.text}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
