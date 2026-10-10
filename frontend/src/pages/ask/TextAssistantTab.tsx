import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Icon } from '../../components/Icon';
import { Button, Card, Chip } from '../../components/ui';
import { VOICE_LANGUAGES } from '../../hooks/useSpeechInput';
import { RECORDER_DENIED, RECORDER_FAILED, useRecorder } from '../../hooks/useRecorder';
import { ApiError } from '../../services/api';
import { useAssistantStatus } from '../../services/assistant';
import { useMe } from '../../services/auth';
import {
  type Line,
  pdfUrl,
  transcribe,
  useAddLine,
  useAddToKnowledge,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useEditLine,
  useRemoveLine,
  useUpdateConversation,
} from '../../services/text';

function LineRow({ conversationId, line }: { conversationId: string; line: Line }) {
  const edit = useEditLine();
  const remove = useRemoveLine();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(line.text);
  return (
    <li className="act" style={{ alignItems: 'flex-start', gap: 10 }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <textarea
            aria-label="Edit line"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ width: '100%', font: 'inherit', padding: 8, borderRadius: 8, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
          />
        ) : (
          <span style={{ whiteSpace: 'pre-wrap' }}>{line.text}</span>
        )}
        <small style={{ display: 'block' }}>{line.source === 'voice' ? 'Voice' : 'Typed'}</small>
      </span>
      <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {editing ? (
          <>
            <Button
              small
              disabled={!text.trim() || edit.isPending}
              onClick={async () => {
                await edit.mutateAsync({ id: conversationId, lineId: line.id, text });
                setEditing(false);
              }}
            >
              Save
            </Button>
            <Button small variant="ghost" onClick={() => { setText(line.text); setEditing(false); }}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button small variant="ghost" aria-label={`Edit line: ${line.text.slice(0, 40)}`} onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button
              small
              variant="ghost"
              aria-label={`Remove line: ${line.text.slice(0, 40)}`}
              disabled={remove.isPending}
              onClick={() => remove.mutate({ id: conversationId, lineId: line.id })}
            >
              Remove
            </Button>
          </>
        )}
      </span>
    </li>
  );
}

function Conversation({ id, onGone }: { id: string; onGone: () => void }) {
  const me = useMe().data;
  const status = useAssistantStatus().data;
  const { data: conversation, isError } = useConversation(id);
  const update = useUpdateConversation();
  const addLine = useAddLine();
  const remove = useDeleteConversation();
  const toKnowledge = useAddToKnowledge();
  const [typed, setTyped] = useState('');
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const language = conversation?.language ?? 'en-IN';

  useEffect(() => {
    if (conversation) setTitle(conversation.title);
  }, [conversation?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  const onTurn = useCallback(
    async (wav: Blob) => {
      setWorking(true);
      setMessage('Turning your speech into text…');
      try {
        const text = await transcribe(wav, language);
        if (text) {
          await addLine.mutateAsync({ id, text, source: 'voice' });
          setMessage('Added. Speak again, or type a line.');
        } else {
          setMessage("I didn't catch any words. Try again, or type a line.");
        }
      } catch (error) {
        setMessage(error instanceof ApiError ? error.message : RECORDER_FAILED);
      } finally {
        setWorking(false);
      }
    },
    [addLine, id, language],
  );
  const recorder = useRecorder((wav) => void onTurn(wav));

  if (isError) return <p className="sub">This conversation is no longer available.</p>;
  if (!conversation) return <p className="sub">Opening…</p>;

  async function submitTyped(event: FormEvent) {
    event.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setTyped('');
    await addLine.mutateAsync({ id, text, source: 'typed' });
  }

  async function addToKnowledge() {
    try {
      const doc = await toKnowledge.mutateAsync({ id });
      setMessage(`Added to the knowledge base as “${doc.title}”. You can find it in the Knowledge Base tab.`);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not add it. Please try again.');
    }
  }

  const speechReady = status?.speech ?? false;
  const micNotice =
    recorder.state === 'denied'
      ? RECORDER_DENIED
      : recorder.state === 'error'
        ? RECORDER_FAILED
        : recorder.recording
          ? `Recording… ${recorder.seconds}s. Press the microphone again to stop.`
          : message;

  return (
    <div className="stack">
      <Card>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="field" style={{ flex: 1, minWidth: 200 }}>
            Title
            <input
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => title.trim() && title !== conversation.title && update.mutate({ id, title })}
            />
          </label>
          <label className="field">
            Language
            <select value={language} onChange={(e) => update.mutate({ id, language: e.target.value })}>
              {VOICE_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '14px 0', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="ib"
            aria-label="Record a turn"
            aria-pressed={recorder.recording}
            disabled={!speechReady || working}
            onClick={() => (recorder.recording ? recorder.stop() : void recorder.start())}
          >
            <Icon name="mic" />
          </button>
          <span className="fine" role="status" aria-live="polite" style={{ margin: 0 }}>
            {speechReady ? micNotice : 'The speech service is not set up, so voice is off. You can type lines instead.'}
          </span>
        </div>

        <form onSubmit={submitTyped} style={{ display: 'flex', gap: 8 }}>
          <input
            aria-label="Type a line"
            placeholder="Type a line…"
            value={typed}
            maxLength={2000}
            onChange={(e) => setTyped(e.target.value)}
            style={{ flex: 1, font: 'inherit', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)' }}
          />
          <Button type="submit" disabled={!typed.trim() || addLine.isPending}>
            Add line
          </Button>
        </form>
      </Card>

      <Card>
        {conversation.lines.length === 0 ? (
          <p className="sub" style={{ margin: 0 }}>
            No lines yet. Speak or type to start.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }} aria-label="Lines">
            {conversation.lines.map((line) => (
              <LineRow key={line.id} conversationId={id} line={line} />
            ))}
          </ul>
        )}
      </Card>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <a className="btn ghost" href={pdfUrl(id)} download>
          Download PDF
        </a>
        {(me?.role === 'advocate' || me?.role === 'admin') && (
          <Button variant="ghost" disabled={conversation.lines.length === 0 || toKnowledge.isPending} onClick={() => void addToKnowledge()}>
            Add to the knowledge base
          </Button>
        )}
        {confirmDelete ? (
          <span role="group" aria-label="Delete this conversation?" style={{ display: 'flex', gap: 8 }}>
            <Button
              onClick={async () => {
                await remove.mutateAsync(id);
                onGone();
              }}
            >
              Yes, delete
            </Button>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              Keep it
            </Button>
          </span>
        ) : (
          <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
            Delete conversation
          </Button>
        )}
      </div>
      {confirmDelete && (
        <p className="fine" role="note">
          Deleting removes it from this tab. Its entry stays in History.
        </p>
      )}
      {message && recorder.state === 'idle' && !speechReady && (
        <p className="fine" role="status">
          {message}
        </p>
      )}
    </div>
  );
}

/** Speak or type a conversation, keep it in your account, download it, or add it to the knowledge base. */
export default function TextAssistantTab() {
  const { data: rows } = useConversations();
  const create = useCreateConversation();
  const [selected, setSelected] = useState<string | null>(null);
  const status = useAssistantStatus().data;

  useEffect(() => {
    if (selected === null && rows && rows.length > 0) setSelected(rows[0].id);
    if (selected !== null && rows && !rows.some((r) => r.id === selected)) setSelected(rows[0]?.id ?? null);
  }, [rows, selected]);

  return (
    <div className="stack" id="text-assistant">
      <p className="advicenotice" role="note" style={{ margin: 0 }}>
        When you record, your voice is sent to the speech service (Sarvam AI) to be turned into text. MrCourt does not
        store the audio; only the text is kept, in your account, visible only to you.
      </p>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button
          disabled={create.isPending}
          onClick={async () => {
            const made = await create.mutateAsync(status ? 'en-IN' : 'en-IN');
            setSelected(made.id);
          }}
        >
          New conversation
        </Button>
        {rows && rows.length > 0 && (
          <div role="group" aria-label="Your conversations" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {rows.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`pill ${selected === r.id ? '' : ''}`.trim()}
                aria-pressed={selected === r.id}
                onClick={() => setSelected(r.id)}
              >
                {r.title} <Chip tone="closed">{r.line_count}</Chip>
              </button>
            ))}
          </div>
        )}
      </div>
      {selected ? (
        <Conversation key={selected} id={selected} onGone={() => setSelected(null)} />
      ) : (
        <p className="sub">You have no conversations yet. Start one with New conversation.</p>
      )}
    </div>
  );
}
