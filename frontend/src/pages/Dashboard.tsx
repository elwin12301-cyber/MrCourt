import { Link, useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { QuickAsk } from '../components/QuickAsk';
import { VoicePanel } from '../components/VoicePanel';
import { Button } from '../components/ui';
import { useMe } from '../services/auth';
import {
  acceptInvitation,
  dateParts,
  timeAgo,
  timeOf,
  useCaseMutation,
  useDashboard,
  useInvitations,
} from '../services/cases';

/** "Adv. Rohan Sharma" -> "Adv. Sharma"; "Anita Sharma" -> "Anita". */
export function greetingName(fullName: string): string {
  const words = fullName.split(/\s+/).filter(Boolean);
  if (/^adv\.?$/i.test(words[0] ?? '') && words.length > 1) {
    return `Adv. ${words[words.length - 1]}`;
  }
  return words[0] ?? '';
}

export function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function formatToday(date: Date): string {
  return new Intl.DateTimeFormat('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function Invitations() {
  const { data } = useInvitations();
  const accept = useCaseMutation(acceptInvitation);
  if (!data?.length) return null;
  return (
    <div className="card">
      <h2 style={{ marginBottom: 14 }}>Case invitations</h2>
      {data.map((invitation) => (
        <div className="act" key={invitation.id} style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ flex: 1 }}>
            Your advocate invited you to view <b>{invitation.case_title}</b>
          </span>
          <Button small onClick={() => accept.mutate(invitation.id)} disabled={accept.isPending}>
            Accept
          </Button>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { data: me } = useMe();
  const { data } = useDashboard();
  const navigate = useNavigate();
  if (!me) return null;
  const now = new Date();
  const isAdvocate = me.role === 'advocate';

  const weekNote = data
    ? ` · ${data.hearings_this_week} hearing${data.hearings_this_week === 1 ? '' : 's'} this week`
    : '';

  return (
    <section className="view" id="dashboard" data-view="dashboard">
      <div>
        <h1>
          {greetingFor(now)}, {greetingName(me.full_name)}
        </h1>
        <p className="sub">
          {formatToday(now)}
          {weekNote}
        </p>
      </div>
      <VoicePanel />
      {!isAdvocate && <Invitations />}
      <div className="row">
        <div className="card stat">
          <b>{data?.active_cases ?? '–'}</b>
          <span>Active cases</span>
        </div>
        <div className="card stat">
          <b>{data?.hearings_this_week ?? '–'}</b>
          <span>Hearings this week</span>
        </div>
        {isAdvocate && (
          <div className="card stat">
            <b>{data?.drafts_to_review ?? '–'}</b>
            <span>Drafts to review</span>
          </div>
        )}
      </div>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="card" style={{ flexBasis: 420, flexGrow: 1.2 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 6,
            }}
          >
            <h2>Upcoming hearings</h2>
            <Link to="/cases" className="back" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
              View all
            </Link>
          </div>
          {data && data.upcoming_hearings.length === 0 && (
            <p className="sub">No hearings scheduled.</p>
          )}
          {data?.upcoming_hearings.map((c) => {
            const { day, month } = dateParts(c.next_hearing_at as string);
            return (
              <button
                key={c.id}
                type="button"
                className="hear"
                onClick={() => navigate(`/cases/${c.id}`)}
              >
                <span className="date">
                  <b>{day}</b>
                  <small>{month}</small>
                </span>
                <span className="t">
                  <b>{c.title}</b>
                  <span>
                    {c.court} · {timeOf(c.next_hearing_at as string)}
                  </span>
                </span>
                <Icon name="chev" />
              </button>
            );
          })}
        </div>
        <div className="stack">
          <QuickAsk />
          <div className="card">
            <h2 style={{ marginBottom: 14 }}>Recent activity</h2>
            {data && data.recent_activity.length === 0 && <p className="sub">Nothing yet.</p>}
            {data?.recent_activity.map((event, i) => (
              <div className="act" key={i}>
                {event.message}
                <span>{timeAgo(event.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
