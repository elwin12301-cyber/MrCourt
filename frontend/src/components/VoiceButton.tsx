import { VOICE_LANGUAGES, type SpeechInput } from '../hooks/useSpeechInput';
import { Icon } from './Icon';

/** The microphone inside a question bar. A real button: reachable, labelled, and pressed while listening. */
export function VoiceButton({ voice }: { voice: SpeechInput }) {
  return (
    <button
      type="button"
      className="ib"
      aria-label="Voice input"
      aria-pressed={voice.listening}
      onClick={voice.toggle}
    >
      <Icon name="mic" />
    </button>
  );
}

/**
 * What voice is doing, announced politely to screen readers, plus the language to speak in.
 * The words are recognised by the browser itself; MrCourt never receives the audio.
 */
export function VoiceStatus({
  voice,
  onDark = false,
  compact = false,
}: {
  voice: SpeechInput;
  onDark?: boolean;
  compact?: boolean;
}) {
  const color = onDark ? { color: 'var(--sand)' } : undefined;
  if (compact) {
    return (
      <p className="fine" role="status" aria-live="polite" style={{ margin: '8px 0 0', ...color }}>
        {voice.notice ?? ''}
      </p>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <p className="fine" role="status" aria-live="polite" style={{ margin: 0, ...color }}>
        {voice.notice ?? ''}
      </p>
      <label className="fine" style={{ display: 'flex', gap: 6, alignItems: 'center', margin: 0, ...color }}>
        Speak in
        <select
          value={voice.language}
          onChange={(e) => voice.setLanguage(e.target.value)}
          disabled={voice.listening}
          style={{ font: 'inherit', fontSize: 12, padding: '2px 6px', borderRadius: 6 }}
        >
          {VOICE_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </label>
      <span className="fine" style={{ margin: 0, ...color }}>
        Your browser turns speech into text; MrCourt never receives the audio. Language support varies by browser.
      </span>
    </div>
  );
}
