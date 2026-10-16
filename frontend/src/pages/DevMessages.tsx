import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

interface DevMessage {
  to: string;
  kind: string;
  channel: string;
  text: string;
  at: string;
}

const KIND_NAME: Record<string, string> = {
  reminder: 'Reminder',
  code: 'Code',
  update: 'Case update',
  activity: 'Client activity',
  reply: 'Reply',
};

/** Development only: the messages that would have been sent by text or WhatsApp (codes, reminders, replies). */
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
        Messages are not really sent while no text-message or WhatsApp service is set up. Here is what would have been sent. This
        page does not exist in production.
      </p>
      {isError && <p role="alert">Not available here: either a real text-message service is set up, or this is not a development setup.</p>}
      {!isError && !isLoading && data?.length === 0 && <p>No messages yet.</p>}
      <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }} aria-label="Messages">
        {data?.map((m, i) => (
          <li key={`${m.at}-${i}`} className="card">
            <div className="fine" style={{ margin: 0 }}>
              To {m.to} · {m.channel === 'whatsapp' ? 'WhatsApp' : 'Text'} · {KIND_NAME[m.kind] ?? 'Message'} ·{' '}
              {new Date(m.at).toLocaleString('en-IN')}
            </div>
            <p style={{ margin: '6px 0 0' }}>{m.text}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
