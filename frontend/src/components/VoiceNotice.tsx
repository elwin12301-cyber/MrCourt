import { useEffect, useRef } from 'react';
import { VOICE_SHORTCUT, useVoice } from '../voice/voiceContext';

/**
 * The plain-language notice shown before voice control is first used (FR-030). Closing it agrees to nothing.
 * The wording says exactly who hears the audio: MrCourt never receives it, and the browser's own speech service
 * may process it under the browser maker's terms.
 */
export function VoiceNotice() {
  const { noticeOpen, agree, decline, error } = useVoice();
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (noticeOpen && !el.open) el.showModal();
    if (!noticeOpen && el.open) el.close();
  }, [noticeOpen]);

  return (
    <dialog ref={dialog} className="vc-notice" aria-labelledby="vc-notice-title" onClose={decline}>
      <h2 id="vc-notice-title">Turn on voice control?</h2>
      <p>
        Voice control lets you use MrCourt by speaking, for example “go to dashboard” or “open cases”. While it is on,
        the microphone listens continuously until you turn it off. The screen always shows when it is listening and the
        last words it heard.
      </p>
      <ul>
        <li>
          <b>Your audio.</b> MrCourt does not receive, record or store it, and does not keep what you say. Your
          browser’s own speech service does the listening; in Chrome and Edge the browser’s maker may process the audio
          under its own privacy terms.
        </li>
        <li>
          <b>Cloud option.</b> Only if you choose it later in Settings, for a language your browser cannot recognise,
          short phrases are sent to MrCourt’s speech service. They are not stored.
        </li>
        <li>
          <b>Safe by design.</b> Deleting, removing, signing out and sending always ask you to say “confirm” first.
          Anything unclear is never acted on.
        </li>
        <li>
          <b>Your control.</b> Turn it off any time with the microphone button, {VOICE_SHORTCUT.label}, or by saying
          “stop listening”. Withdraw your agreement in Settings. The mouse and keyboard always keep working.
        </li>
      </ul>
      {error && <p role="alert">{error}</p>}
      <div className="vc-notice-actions">
        <button type="button" className="btn" onClick={() => void agree()}>
          Agree and turn on
        </button>
        <button type="button" className="btn ghost" onClick={decline}>
          Not now
        </button>
      </div>
    </dialog>
  );
}
