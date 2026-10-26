import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';
import { ApiError } from '../services/api';
import { dayOf } from '../services/cases';
import { CLIENT_DASHBOARD_KEY, askLawyer, markReplyRead, questionsKey, useMyQuestions } from '../services/client';
import { Button, Disclaimer } from './ui';

/** Send your lawyer a question or ask for an update. Only you and your lawyer can see this. */
export function AskLawyer({ caseId, available }: { caseId: string; available: boolean }) {
  const client = useQueryClient();
  const { data: questions } = useMyQuestions(caseId);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  // Replies that were unread when they first appeared are labelled "New" for this visit.
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());

  // Mark replies read on the server as soon as they are on screen, but keep their "New" label
  // until the client leaves the page.
  useEffect(() => {
    const unread = (questions ?? []).filter((q) => q.reply_text && !q.reply_read && !fresh.has(q.id));
    if (unread.length === 0) return;
    setFresh((previous) => new Set([...previous, ...unread.map((q) => q.id)]));
    for (const q of unread) void markReplyRead(q.id);
  }, [questions, fresh]);

  async function send(kind: 'question' | 'update_request', body?: string) {
    setBusy(true);
    setNote(null);
    try {
      await askLawyer(caseId, kind, body);
      setText('');
      await client.invalidateQueries({ queryKey: questionsKey(caseId) });
      await client.invalidateQueries({ queryKey: CLIENT_DASHBOARD_KEY });
      setNote(kind === 'question' ? 'Sent to your lawyer.' : 'Update requested.');
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : 'Could not send. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send('question', text);
  }

  return (
    <div className="card" id="ask-lawyer" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2>Ask your lawyer</h2>
      <p className="fine" style={{ margin: 0 }}>
        Only you and your lawyer can see these messages. MrCourt does not answer them.
      </p>
      {available ? (
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <label className="field" htmlFor="lawyer-question">
            Your question
            <textarea
              id="lawyer-question"
              rows={3}
              maxLength={2000}
              value={text}
              onChange={(e) => { setText(e.target.value); setNote(null); }}
              style={{ font: 'inherit', padding: 12, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
            />
          </label>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button type="submit" small data-voice-risk="send" disabled={busy || !text.trim()}>Send question</Button>
            <Button small variant="ghost" disabled={busy} onClick={() => void send('update_request')}>
              Ask for an update
            </Button>
            {note && <span className="fine" role="status">{note}</span>}
          </div>
        </form>
      ) : (
        <p className="sub" style={{ margin: 0 }}>
          Your lawyer is no longer available on MrCourt, so new questions cannot be sent.
        </p>
      )}

      {questions && questions.length > 0 && (
        <div>
          {questions.map((q) => (
            <div className="act" key={q.id}>
              <b>{q.kind === 'update_request' ? 'You asked for an update' : q.text}</b>
              <span>Sent {dayOf(q.sent_at)}</span>
              {q.reply_text ? (
                <p style={{ margin: '8px 0 0' }}>
                  <span className="eyebrow">
                    Your lawyer replied {q.replied_at ? dayOf(q.replied_at) : ''}
                    {fresh.has(q.id) && <span className="badge" style={{ marginLeft: 8 }}>New</span>}
                  </span>
                  <br />
                  {q.reply_text}
                </p>
              ) : (
                <span style={{ fontWeight: 600 }}>Sent</span>
              )}
            </div>
          ))}
        </div>
      )}
      <Disclaimer />
    </div>
  );
}
