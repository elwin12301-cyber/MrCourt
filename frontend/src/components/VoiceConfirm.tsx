import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { openDialog } from '../voice/controls';
import { useVoice } from '../voice/voiceContext';

/**
 * Asks before a risky action runs (FR-016, FR-017): what is about to happen, and "Confirm" / "Cancel". The same
 * question is spoken, and the person can answer by voice ("confirm", "cancel"), the buttons, or Escape. Focus goes
 * to Cancel, so a stray Enter cannot confirm. If a native dialog is open the prompt is drawn inside it, because
 * the rest of the page is blocked while it is open.
 */
export function VoiceConfirm() {
  const { confirmPrompt, answerPrompt } = useVoice();
  const cancel = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirmPrompt) cancel.current?.focus();
  }, [confirmPrompt]);

  if (!confirmPrompt) return null;
  const host = openDialog() ?? document.body;
  return createPortal(
    <div className="vc-confirm" role="alertdialog" aria-label="Please confirm" aria-describedby="vc-confirm-text" data-voice-ui>
      <p id="vc-confirm-text">{confirmPrompt}</p>
      <div className="vc-confirm-actions">
        <button type="button" className="btn small" onClick={() => answerPrompt(true)}>
          Confirm
        </button>
        <button ref={cancel} type="button" className="btn small ghost" onClick={() => answerPrompt(false)}>
          Cancel
        </button>
      </div>
    </div>,
    host,
  );
}
