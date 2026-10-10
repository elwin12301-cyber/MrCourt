import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AnswerMessage,
  ErrorMessage,
  PendingMessage,
  UserMessage,
} from '../../components/ChatMessage';
import { Icon } from '../../components/Icon';
import { VoiceButton, VoiceStatus } from '../../components/VoiceButton';
import { Pill } from '../../components/ui';
import { useServerVoice } from '../../hooks/useServerVoice';
import { useSpeechInput } from '../../hooks/useSpeechInput';
import { ApiError } from '../../services/api';
import { ASSISTANT_SUGGESTIONS, type AssistantReply, runAssistant, useAssistantStatus } from '../../services/assistant';
import { useMe } from '../../services/auth';
import { type Answer, type InputMethod, SUGGESTIONS, askQuestion } from '../../services/questions';

type Entry =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'pending'; assistant: boolean }
  | { id: number; kind: 'error'; text: string }
  | { id: number; kind: 'answer'; answer: Answer | AssistantReply };

type CarriedState = { caseId?: string; question?: string; assistant?: boolean; voice?: boolean } | null;

export default function AskTab() {
  const location = useLocation();
  const navigate = useNavigate();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [assistantMode, setAssistantMode] = useState(false);
  const nextId = useRef(1);
  const bottom = useRef<HTMLDivElement>(null);
  const status = useAssistantStatus();
  const me = useMe().data;
  const state = location.state as CarriedState;
  const caseId = state?.caseId;
  const assistantAvailable = status.data?.assistant ?? false;

  const ask = useCallback(
    async (raw: string, viaAssistant: boolean, method: InputMethod = 'typed') => {
      const text = raw.trim();
      if (!text) return;
      const userId = nextId.current++;
      const pendingId = nextId.current++;
      setEntries((e) => [
        ...e,
        { id: userId, kind: 'user', text },
        { id: pendingId, kind: 'pending', assistant: viaAssistant },
      ]);
      setBusy(true);
      let replacement: Entry;
      try {
        const answer = viaAssistant ? await runAssistant(text, method) : await askQuestion(text, caseId, method);
        replacement = { id: pendingId, kind: 'answer', answer };
      } catch (error) {
        replacement = {
          id: pendingId,
          kind: 'error',
          text:
            error instanceof ApiError && error.status === 429
              ? 'You are asking very quickly. Please wait a moment and try again.'
              : 'Something went wrong while looking that up. Please try again.',
        };
      }
      setEntries((e) => e.map((x) => (x.id === pendingId ? replacement : x)));
      setBusy(false);
    },
    [caseId],
  );

  // A question carried over from the dashboard quick-ask card or from History ("Ask again") is
  // asked once, then cleared so a refresh does not repeat it.
  const carried = state?.question;
  const carriedAssistant = state?.assistant ?? false;
  const carriedVoice = state?.voice ?? false;
  const handled = useRef(false);
  useEffect(() => {
    if (carried && !handled.current && (!carriedAssistant || status.data)) {
      handled.current = true;
      navigate(location.pathname, { replace: true, state: caseId ? { caseId } : null });
      const viaAssistant = carriedAssistant && (status.data?.assistant ?? false);
      setAssistantMode(viaAssistant);
      void ask(carried, viaAssistant, carriedVoice ? 'voice' : 'typed');
    }
  }, [carried, carriedAssistant, carriedVoice, status.data, ask, navigate, location.pathname, caseId]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'nearest' });
  }, [entries]);

  const [serverVoiceOn, setServerVoiceOn] = useState(false);
  const setText = useCallback((t: string) => setInput(t), []);
  const browserVoice = useSpeechInput(setText);
  const serverVoice = useServerVoice(setText, browserVoice.language, browserVoice.setLanguage);
  const speechReady = status.data?.speech ?? false;
  const voice = serverVoiceOn && speechReady ? serverVoice : browserVoice;

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = input;
    const method: InputMethod = voice.usedVoice ? 'voice' : 'typed';
    setInput('');
    voice.clearUsedVoice();
    void ask(value, assistantMode, method);
  }

  const suggestions = assistantMode
    ? ASSISTANT_SUGGESTIONS[me?.role === 'petitioner' ? 'petitioner' : 'advocate']
    : SUGGESTIONS;

  return (
    <>
      {status.data?.notice && (
        <p className="fine" role="note" id="mode-note">
          {status.data.notice}
        </p>
      )}
      {status.data && (
        <p className="fine" role="note" id="search-note">
          {status.data.search === 'meaning'
            ? 'Search: keywords and meaning together, so loosely worded and Tamil questions can find the right passage.'
            : 'Search: keywords only. Meaning-based search is not set up, so loosely worded questions may miss.'}
        </p>
      )}
      <div className="modes" role="group" aria-label="How to ask">
        <Pill pressed={!assistantMode} onClick={() => setAssistantMode(false)}>
          Answer
        </Pill>
        <Pill
          pressed={assistantMode}
          disabled={!assistantAvailable}
          onClick={() => setAssistantMode(true)}
          title={assistantAvailable ? undefined : 'The assistant needs an AI service, which is not set up.'}
        >
          Assistant
        </Pill>
        <span className="fine" style={{ margin: 0 }}>
          {assistantMode
            ? 'The assistant can look things up in your cases and the knowledge base, and can propose a draft. It never changes anything until you confirm.'
            : 'Answers come from the knowledge base and cite their sources.'}
        </span>
      </div>
      {assistantMode && (
        <p className="fine" role="note" id="assistant-privacy">
          In Assistant mode, your request and the case details it needs are sent to the AI service that writes the reply.
        </p>
      )}
      <div className="chat" id="chat" aria-live="polite">
        {entries.map((entry) => {
          switch (entry.kind) {
            case 'user':
              return <UserMessage key={entry.id} text={entry.text} />;
            case 'pending':
              return <PendingMessage key={entry.id} assistant={entry.assistant} />;
            case 'error':
              return <ErrorMessage key={entry.id} text={entry.text} />;
            case 'answer':
              return <AnswerMessage key={entry.id} answer={entry.answer} askLawyerHref={caseId ? `/cases/${caseId}#ask-lawyer` : '/cases'} />;
          }
        })}
        <div ref={bottom} />
      </div>
      <div className="suggest" id="suggest">
        {suggestions.map((s) => (
          <Pill key={s.label} disabled={busy} onClick={() => void ask(s.question, assistantMode)}>
            {s.label}
          </Pill>
        ))}
      </div>
      <form className="bar" id="askForm" style={{ maxWidth: 820 }} onSubmit={submit}>
        <input
          id="askInput"
          aria-label={assistantMode ? 'Ask the assistant' : 'Ask a legal question'}
          placeholder={assistantMode ? 'Ask the assistant to look something up…' : 'Ask a legal question…'}
          autoComplete="off"
          maxLength={2000}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <VoiceButton voice={voice} />
        <button className="ib send" aria-label="Send" disabled={busy || !input.trim()}>
          <Icon name="send" />
        </button>
      </form>
      <VoiceStatus voice={voice} />
      {speechReady && (
        <label className="fine" style={{ display: 'flex', gap: 8, alignItems: 'center', margin: 0 }}>
          <input type="checkbox" checked={serverVoiceOn} onChange={(e) => setServerVoiceOn(e.target.checked)} />
          Better for Tamil: use the speech service (Sarvam AI). Your voice is sent to it to be turned into text, and
          MrCourt does not store it.
        </label>
      )}
    </>
  );
}
