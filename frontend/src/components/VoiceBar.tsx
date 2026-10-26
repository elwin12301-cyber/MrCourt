import { Icon } from './Icon';
import { VOICE_SHORTCUT, useVoice } from '../voice/voiceContext';
import type { VoiceStatus } from '../voice/types';

export const STATUS_TEXT: Record<VoiceStatus, string> = {
  off: 'Microphone is off',
  starting: 'Starting…',
  listening: 'Listening…',
  paused: 'Paused – the microphone is not listening right now',
  confirming: 'Waiting for your answer – say confirm or cancel',
  dictating: 'Dictating – say “stop dictating” when done',
};

/**
 * The voice control launcher and bar, shown on every screen (FR-001, FR-002). Off: one microphone button.
 * On: the microphone, a status, the last words heard, and the few controls that matter. A real button with a
 * visible name and focus, so keyboard and screen-reader users have it too.
 */
export function VoiceBar() {
  const v = useVoice();

  if (!v.on) {
    return (
      <div className="vc-dock" data-voice-ui>
        {v.error && (
          <p className="vc-error" role="status">
            {v.error}
          </p>
        )}
        <button
          type="button"
          className="vc-launch"
          aria-pressed="false"
          aria-label="Turn on voice control"
          title={`Turn on voice control (${VOICE_SHORTCUT.label})`}
          onClick={v.toggle}
        >
          <Icon name="mic" />
          <span className="vc-launch-text">Voice</span>
        </button>
      </div>
    );
  }

  return (
    <div className="vc-dock vc-on" data-voice-ui role="region" aria-label="Voice control">
      <button
        type="button"
        className="vc-mic"
        aria-pressed="true"
        aria-label="Voice control is on. Press to turn it off"
        title={`Turn off voice control (${VOICE_SHORTCUT.label})`}
        onClick={v.toggle}
      >
        <Icon name="mic" />
      </button>
      <div className="vc-text">
        <p className="vc-status" role="status" aria-live="polite">
          <span className={`vc-dot ${v.status}`} aria-hidden="true" />
          {STATUS_TEXT[v.status]}
        </p>
        <p className="vc-heard">
          {v.lastHeard ? <>Heard: “{v.lastHeard}”</> : <>Say “what can I say” for help.</>}
        </p>
        {v.result && (
          <p className={`vc-result ${v.result.kind}`} role="status" aria-live="polite">
            {v.result.message}
          </p>
        )}
      </div>
      <div className="vc-actions">
        <button type="button" className="btn small ghost" aria-pressed={!!v.numbers} onClick={() => v.showNumbers(!v.numbers)}>
          Numbers
        </button>
        <button type="button" className="btn small ghost" aria-pressed={v.replies} onClick={() => v.setReplies(!v.replies)}>
          Replies
        </button>
        <button type="button" className="btn small ghost" onClick={v.openHelp}>
          Help
        </button>
        <button type="button" className="btn small" onClick={v.stop}>
          Stop
        </button>
      </div>
    </div>
  );
}
