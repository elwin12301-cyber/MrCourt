import { type FormEvent, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSpeechInput } from '../hooks/useSpeechInput';
import { Icon } from './Icon';
import { VoiceButton, VoiceStatus } from './VoiceButton';

/** Navy "Ask MrCourt anything" card from the dashboard. */
export function QuickAsk() {
  const navigate = useNavigate();
  const [value, setValue] = useState('');
  const voice = useSpeechInput(useCallback((t: string) => setValue(t), []));

  function submit(event: FormEvent) {
    event.preventDefault();
    const question = value.trim();
    if (!question) return;
    navigate('/ask', { state: { question, voice: voice.usedVoice } });
    voice.clearUsedVoice();
  }

  return (
    <form className="askcard" id="quickAsk" onSubmit={submit}>
      <h2>Ask MrCourt anything about Indian law</h2>
      <div className="bar">
        <input
          id="qa"
          aria-label="Ask a legal question"
          placeholder="e.g. Bail conditions under BNSS…"
          autoComplete="off"
          maxLength={2000}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <VoiceButton voice={voice} />
        <button className="ib send" aria-label="Ask">
          <Icon name="send" />
        </button>
      </div>
      <VoiceStatus voice={voice} onDark compact />
    </form>
  );
}
