import { Icon } from './Icon';
import { STATUS_TEXT } from './VoiceBar';
import { packFor } from '../voice/lang';
import { VOICE_SHORTCUT, useVoice } from '../voice/voiceContext';

/**
 * The voice panel on every dashboard (FR-002b), laid out like the reference image: a large microphone tile, a
 * headline, plain instructions, a status line, and an "I heard you say" card with the last phrase, what happened,
 * and a phrase to try. Uses the app's tokens, so it follows the light and dark themes.
 */
export function VoicePanel() {
  const v = useVoice();
  const pack = packFor(v.language);
  const heard = v.lastHeard || `Try “${pack.suggestion}”`;

  return (
    <section className="vc-panel" aria-labelledby="vc-panel-title">
      <button
        type="button"
        className="vc-tile"
        aria-pressed={v.on}
        aria-label={v.on ? 'Microphone: voice control is on, press to turn it off' : 'Microphone: turn on voice control'}
        title={`${v.on ? 'Turn off' : 'Turn on'} voice control (${VOICE_SHORTCUT.label})`}
        onClick={v.toggle}
      >
        <Icon name="mic" />
      </button>
      <div>
        <p className="eyebrow">Voice-controlled workspace</p>
        <h2 id="vc-panel-title">Your voice is the remote</h2>
        <p>
          Tap the microphone and tell the app where to go. Keep this tab open and allow the microphone when asked. Say
          “stop listening” to turn it off.
        </p>
        <p className="vc-status" role="status" aria-live="polite">
          <span className={`vc-dot ${v.status}`} aria-hidden="true" />
          {STATUS_TEXT[v.status]}
        </p>
        {v.error && <p role="alert">{v.error}</p>}
        <div className="vc-links">
          <button type="button" className="btn small ghost" onClick={v.openHelp}>
            What can I say?
          </button>
          <button
            type="button"
            className="btn small ghost"
            aria-pressed={!!v.numbers}
            disabled={!v.on}
            onClick={() => v.showNumbers(!v.numbers)}
          >
            {v.numbers ? 'Hide numbers' : 'Show numbers'}
          </button>
        </div>
      </div>
      <div className="vc-heard-card">
        <p className="label">I heard you say</p>
        <p className="said">{heard}</p>
        {v.result && <p className="note">{v.result.message}</p>}
        {v.on && v.engine === 'cloud' && (
          <p className="note">Using the cloud speech service: short phrases are sent for recognition and are not stored.</p>
        )}
        <p className="note">Voice recognition works best in Chrome or Edge over a secure connection or localhost.</p>
      </div>
    </section>
  );
}
