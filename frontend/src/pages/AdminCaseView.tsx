import { Link, useParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Chip } from '../components/ui';
import { useCaseInFull } from '../services/admin';
import { dateTimeOf, dayOf, fileSize } from '../services/cases';

const Shared = ({ shared }: { shared: boolean }) => (
  <Chip tone={shared ? 'ok' : 'soon'}>{shared ? 'Visible to clients' : 'Private'}</Chip>
);

/** One case, in full and read-only, including what is private to the advocate. */
export default function AdminCaseView() {
  const { caseId } = useParams();
  const { data: c, isLoading, error } = useCaseInFull(caseId);

  if (isLoading) return <section className="view" aria-busy="true" />;
  if (error || !c) {
    return (
      <section className="view">
        <Link to="/admin/cases" className="back">
          <Icon name="back" />
          All cases
        </Link>
        <h1>Case not found</h1>
      </section>
    );
  }

  return (
    <section className="view" id="admin-case" data-view="admin-case">
      <Link to="/admin/cases" className="back">
        <Icon name="back" />
        All cases
      </Link>
      <div>
        <h1>{c.title}</h1>
        <p className="sub">
          CNR {c.cnr_number} · {c.court}
        </p>
        <p style={{ margin: '10px 0 0', display: 'flex', gap: 8 }}>
          <Chip tone={c.status === 'closed' ? 'closed' : 'ok'}>{c.status === 'closed' ? 'Closed' : 'Open'}</Chip>
        </p>
      </div>
      <p className="advicenotice" role="note" style={{ margin: 0 }}>
        This page shows everything on the case, including what is private to the advocate. Opening it is recorded in
        the audit log. You can read it here but cannot change it.
      </p>

      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="stack">
          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Summary</h2>
            <div className="act">
              <span>Advocate</span>
              <Link to={`/admin/advocates/${c.advocate.id}`}>
                <b>{c.advocate.name}</b>
              </Link>
            </div>
            {c.stage && (
              <div className="act">
                <span>Stage</span>
                {c.stage}
              </div>
            )}
            {c.court_room && (
              <div className="act">
                <span>Court room</span>
                {c.court_room}
              </div>
            )}
            <div className="act">
              <span>Status shown to clients</span>
              {c.client_status ? c.client_status.replace(/_/g, ' ') : 'Not set'}
              {c.client_status_changed_at ? ` (since ${dayOf(c.client_status_changed_at)})` : ''}
            </div>
            {c.parties.map((p, i) => (
              <div className="act" key={i}>
                <span style={{ textTransform: 'capitalize' }}>{p.side}</span>
                {p.name}
                {p.is_client ? ' (advocate’s client)' : ''}
              </div>
            ))}
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Advocate’s private notes</h2>
            <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{c.notes || 'No notes.'}</p>
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Hearings</h2>
            {c.hearings.length === 0 && <p className="sub">No hearings.</p>}
            {c.hearings.map((h) => (
              <div className="act" key={h.id}>
                <b>{dateTimeOf(h.scheduled_at)}</b>
                <span>{[h.purpose, h.court_room].filter(Boolean).join(' · ') || 'Hearing'}</span>
                {h.outcome && (
                  <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', color: 'var(--ink)' }}>
                    Outcome: {h.outcome} <Shared shared={h.outcome_shared} />
                  </span>
                )}
              </div>
            ))}
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Timeline</h2>
            {c.timeline.length === 0 && <p className="sub">Nothing on the timeline.</p>}
            {c.timeline.map((e) => (
              <div className="act" key={e.id} style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <span style={{ flex: 1, minWidth: 200, color: 'var(--ink)', fontSize: 14 }}>
                  {e.text}
                  <span style={{ display: 'block', color: 'var(--muted)', fontSize: 12 }}>{dayOf(e.occurred_at)}</span>
                </span>
                <Shared shared={e.shared_with_client} />
              </div>
            ))}
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Documents</h2>
            {c.documents.length === 0 && <p className="sub">No documents.</p>}
            {c.documents.map((d) => (
              <div className="act" key={d.id} style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ color: 'var(--ink)', fontSize: 14 }}>
                  <a href={`/api/v1/admin/cases/${c.id}/documents/${d.id}/download`}>
                    <b>{d.file_name}</b>
                  </a>
                  <span style={{ display: 'block', color: 'var(--muted)', fontSize: 12 }}>{fileSize(d.size_bytes)} · download is recorded</span>
                </span>
                <Shared shared={d.shared_with_client} />
              </div>
            ))}
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Clients on this case</h2>
            {c.clients.length === 0 && <p className="sub">No clients invited.</p>}
            {c.clients.map((cl) => (
              <div className="act" key={cl.id}>
                <b>{cl.name}</b>
                <span>{cl.accepted_at ? `Can see the case since ${dayOf(cl.accepted_at)}` : 'Invitation not accepted yet'}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h2 style={{ marginBottom: 10 }}>Clients’ questions and replies</h2>
            {c.client_questions.length === 0 && <p className="sub">No questions.</p>}
            {c.client_questions.map((q) => (
              <div className="act" key={q.id}>
                <b>{q.client_name}</b>
                <span>{q.kind === 'update_request' ? 'Asked for an update' : q.text} · {dayOf(q.sent_at)}</span>
                {q.reply_text ? (
                  <p style={{ margin: '6px 0 0' }}>
                    <span className="eyebrow">Advocate’s reply</span>
                    <br />
                    {q.reply_text}
                  </p>
                ) : (
                  <span style={{ fontWeight: 600 }}>No reply yet</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
