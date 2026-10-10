import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, api } from '../services/api';
import { Button } from './ui';

const RESEND_AFTER_SECONDS = 30;

/** "+919876543210" shown as "•••• 3210" so the number is not displayed in full. */
export const maskPhone = (phone: string | null | undefined) => (phone ? `•••• ${phone.slice(-4)}` : 'your mobile number');

/**
 * Texts a 6-digit code to the phone on the account and checks what the person types back.
 * Used right after sign-up and from Settings.
 */
export function PhoneCodeStep({
  phone,
  onVerified,
  onSkip,
  skipLabel = 'Verify later',
}: {
  phone: string | null | undefined;
  onVerified: () => void;
  onSkip?: () => void;
  skipLabel?: string;
}) {
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [development, setDevelopment] = useState(false);
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(RESEND_AFTER_SECONDS);
  const requested = useRef(false);

  const send = useCallback(async () => {
    setError(null);
    try {
      const reply = await api.post<{ detail: string; delivery?: string }>('/auth/phone/request');
      setDevelopment(reply.delivery === 'development');
      setNote(`We texted a code to ${maskPhone(phone)}. It works for 10 minutes.`);
      setWait(RESEND_AFTER_SECONDS);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not send the code. Please try again.');
    }
  }, [phone]);

  useEffect(() => {
    if (requested.current) return;
    requested.current = true;
    void send();
  }, [send]);

  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post('/auth/phone/verify', { code });
      onVerified();
    } catch (e) {
      setError(e instanceof ApiError && e.status === 400 ? 'That code is not right, or it has expired. Check it or ask for a new one.' : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={verify} aria-label="Verify your mobile number" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p className="fine" role="status" style={{ margin: 0 }}>
        {note ?? 'Sending a code…'}
      </p>
      {development && (
        <p className="fine" role="note" style={{ margin: 0 }}>
          No text-message service is set up, so nothing was really sent. In development, read the code on the{' '}
          <Link to="/dev/messages" target="_blank" rel="noreferrer">
            Development messages
          </Link>{' '}
          page.
        </p>
      )}
      <label className="field" htmlFor="phone-code">
        6-digit code
        <input
          id="phone-code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          required
        />
      </label>
      {error && (
        <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600, margin: 0 }}>
          {error}
        </p>
      )}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Button type="submit" disabled={busy || code.length !== 6}>
          Verify
        </Button>
        <Button variant="ghost" disabled={wait > 0} onClick={() => void send()}>
          {wait > 0 ? `Resend code in ${wait}s` : 'Resend code'}
        </Button>
        {onSkip && (
          <Button variant="ghost" onClick={onSkip}>
            {skipLabel}
          </Button>
        )}
      </div>
    </form>
  );
}
