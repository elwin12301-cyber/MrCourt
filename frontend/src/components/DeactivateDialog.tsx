import { useEffect, useRef, useState } from 'react';
import { deactivateAccount, errorText } from '../services/account';
import { Button } from './ui';

/** Confirms deactivation, stating plainly what is removed and what is kept (FR-015). */
export function DeactivateDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      setUnderstood(false);
      setError(null);
      el.showModal();
    }
    if (!open && el.open) el.close();
  }, [open]);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await deactivateAccount();
      onDone();
    } catch (e) {
      setError(errorText(e, 'Could not deactivate the account. Please try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby="deactivate-title"
      onClose={onClose}
      style={{
        border: '1px solid var(--line)',
        borderRadius: 14,
        padding: 24,
        maxWidth: 480,
        background: 'var(--surface)',
        color: 'var(--ink)',
      }}
    >
      <h2 id="deactivate-title" style={{ marginBottom: 12 }}>
        Deactivate your account?
      </h2>
      <p>
        You will be signed out and will not be able to sign in again. Your name, contact details,
        settings and question history will be removed.
      </p>
      <p>
        <b>Case records are kept.</b> Cases, hearings, documents and drafts are retained for legal
        record-keeping and are not deleted when you deactivate.
      </p>
      <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', margin: '16px 0' }}>
        <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
        <span>I understand that case records will be kept.</span>
      </label>
      {error && (
        <p className="fine" role="alert">
          {error}
        </p>
      )}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
        <Button variant="ghost" small onClick={onClose}>
          Cancel
        </Button>
        <Button small disabled={!understood || busy} onClick={() => void confirm()}>
          Deactivate my account
        </Button>
      </div>
    </dialog>
  );
}
