import { type FormEvent, useEffect, useState } from 'react';
import { ApiError } from '../services/api';
import { dayOf, useCaseMutation } from '../services/cases';
import { CLIENT_STATUS_LABEL, CLIENT_STATUS_OPTIONS, type ClientStatus } from '../services/client';
import {
  ALWAYS_VISIBLE,
  addTimelineNote,
  postClientUpdate,
  replyToClient,
  setClientStatus,
  setEntrySharing,
  useClientQuestions,
  useTimeline,
} from '../services/clientAdmin';
import { Button, Chip } from './ui';

const textarea = {
  font: 'inherit',
  padding: 12,
  borderRadius: 10,
  border: '1px solid var(--line)',
  background: 'var(--surface)',
  color: 'var(--ink)',
} as const;

function message(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback;
}

function StatusControl({ caseId, current, changedAt }: { caseId: string; current: ClientStatus | null; changedAt: string | null }) {
  const [choice, setChoice] = useState<ClientStatus | ''>(current ?? '');
  const [note, setNote] = useState<string | null>(null);

  // Follow the saved status (for example after a refresh) without losing the confirmation message.
  useEffect(() => {
    setChoice(current ?? '');
  }, [current]);
  const save = useCaseMutation((s: ClientStatus) => setClientStatus(caseId, s));

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2>Status clients see</h2>
      <p className="sub" style={{ margin: 0 }}>
        {current && changedAt
          ? `Clients currently see “${CLIENT_STATUS_LABEL[current]}”, set ${dayOf(changedAt)}.`
          : 'No status has been set yet, so clients are told your lawyer has not shared one.'}
      </p>
      <label className="field" htmlFor="client-status">
        Client-facing status
        <select id="client-status" value={choice} onChange={(e) => { setChoice(e.target.value as ClientStatus); setNote(null); }}>
          {!current && <option value="" disabled>Choose a status</option>}
          {CLIENT_STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{CLIENT_STATUS_LABEL[s]}</option>
          ))}
        </select>
      </label>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button
          small
          disabled={save.isPending || !choice || choice === current}
          onClick={async () => {
            try {
              await save.mutateAsync(choice as ClientStatus);
              setNote('Status updated. Clients have been told.');
            } catch (e) {
              setNote(message(e, 'Could not update the status.'));
            }
          }}
        >
          Update status
        </Button>
        {note && <span className="fine" role="status">{note}</span>}
      </div>
      <p className="fine" style={{ margin: 0 }}>
        Choosing “Closed” also closes the case. Anything more specific goes in a short update below.
      </p>
    </div>
  );
}

function UpdateForm({ caseId }: { caseId: string }) {
  const [text, setText] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const send = useCaseMutation((m: string) => postClientUpdate(caseId, m));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setNote(null);
    try {
      await send.mutateAsync(text.trim());
      setText('');
      setNote('Update sent. Clients have been told.');
    } catch (e) {
      setNote(message(e, 'Could not send the update.'));
    }
  }

  return (
    <form className="card" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2>Write an update for clients</h2>
      <label className="field" htmlFor="client-update">
        Short update, in plain language
        <textarea id="client-update" rows={3} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} style={textarea} required />
      </label>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button type="submit" small disabled={send.isPending || !text.trim()}>Send update</Button>
        {note && <span className="fine" role="status">{note}</span>}
      </div>
    </form>
  );
}

function InternalTimeline({ caseId }: { caseId: string }) {
  const { data, isLoading } = useTimeline(caseId);
  const [text, setText] = useState('');
  const [share, setShare] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const add = useCaseMutation((v: { text: string; shared: boolean }) => addTimelineNote(caseId, v.text, v.shared));
  const toggle = useCaseMutation((v: { id: string; shared: boolean }) => setEntrySharing(caseId, v.id, v.shared));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setNote(null);
    try {
      await add.mutateAsync({ text: text.trim(), shared: share });
      setText('');
      setShare(false);
    } catch (e) {
      setNote(message(e, 'Could not add the note.'));
    }
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <h2>Case timeline</h2>
      <p className="fine" style={{ margin: 0 }}>
        Entries marked “Visible to clients” can be seen by them. Everything else stays private to you.
      </p>
      {!isLoading && data?.length === 0 && <p className="sub">Nothing on the timeline yet.</p>}
      <ol className="tl">
        {data?.map((entry) => (
          <li key={entry.id} style={{ flexWrap: 'wrap' }}>
            <time dateTime={entry.occurred_at}>{dayOf(entry.occurred_at)}</time>
            <span style={{ flex: 1, minWidth: 180 }}>{entry.text}</span>
            <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Chip tone={entry.shared_with_client ? 'active' : 'closed'}>
                {entry.shared_with_client ? 'Visible to clients' : 'Private'}
              </Chip>
              {!ALWAYS_VISIBLE.has(entry.kind) && (
                <Button
                  small
                  variant="ghost"
                  disabled={toggle.isPending}
                  aria-label={`${entry.shared_with_client ? 'Make private' : 'Share with clients'}: ${entry.text.slice(0, 40)}`}
                  onClick={() => toggle.mutate({ id: entry.id, shared: !entry.shared_with_client })}
                >
                  {entry.shared_with_client ? 'Make private' : 'Share'}
                </Button>
              )}
            </span>
          </li>
        ))}
      </ol>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label className="field" htmlFor="timeline-note">
          Add a note to the timeline
          <textarea id="timeline-note" rows={2} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} style={textarea} />
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
          Share this note with clients
        </label>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Button type="submit" small variant="ghost" disabled={add.isPending || !text.trim()}>Add note</Button>
          {note && <span className="fine" role="alert">{note}</span>}
        </div>
      </form>
    </div>
  );
}

function QuestionsInbox({ caseId }: { caseId: string }) {
  const { data } = useClientQuestions(caseId);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const reply = useCaseMutation((v: { id: string; text: string }) => replyToClient(v.id, v.text));
  const waiting = data?.filter((q) => !q.reply_text).length ?? 0;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }} id="client-questions">
      <h2>Questions from clients {waiting > 0 && <span className="badge">{waiting} waiting</span>}</h2>
      <p className="fine" style={{ margin: 0 }}>
        Each client's question and your reply are private to that client. Other clients on the case never see them.
      </p>
      {data?.length === 0 && <p className="sub">No questions yet.</p>}
      {data?.map((q) => (
        <div className="act" key={q.id}>
          <b>{q.client_name}</b>
          <span>{q.kind === 'update_request' ? 'Asked for an update' : q.text} · {dayOf(q.sent_at)}</span>
          {q.reply_text ? (
            <p style={{ margin: '8px 0 0' }}><span className="eyebrow">Your reply</span><br />{q.reply_text}</p>
          ) : (
            <form
              style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}
              onSubmit={async (event) => {
                event.preventDefault();
                setErrors((e) => ({ ...e, [q.id]: '' }));
                try {
                  await reply.mutateAsync({ id: q.id, text: (drafts[q.id] ?? '').trim() });
                  setDrafts((d) => ({ ...d, [q.id]: '' }));
                } catch (err) {
                  setErrors((e) => ({ ...e, [q.id]: message(err, 'Could not send the reply.') }));
                }
              }}
            >
              <label className="field" htmlFor={`reply-${q.id}`}>
                Reply to {q.client_name}
                <textarea
                  id={`reply-${q.id}`}
                  rows={2}
                  maxLength={2000}
                  value={drafts[q.id] ?? ''}
                  onChange={(e) => setDrafts((d) => ({ ...d, [q.id]: e.target.value }))}
                  style={textarea}
                />
              </label>
              {errors[q.id] && <p className="fine" role="alert">{errors[q.id]}</p>}
              <div><Button type="submit" small disabled={reply.isPending || !(drafts[q.id] ?? '').trim()}>Send reply</Button></div>
            </form>
          )}
        </div>
      ))}
    </div>
  );
}

/** Everything an advocate controls about what clients see, in one place. */
export function ClientViewPanel({ caseId, current, changedAt }: { caseId: string; current: ClientStatus | null; changedAt: string | null }) {
  return (
    <div className="stack">
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <StatusControl caseId={caseId} current={current} changedAt={changedAt} />
        <UpdateForm caseId={caseId} />
      </div>
      <QuestionsInbox caseId={caseId} />
      <InternalTimeline caseId={caseId} />
    </div>
  );
}
