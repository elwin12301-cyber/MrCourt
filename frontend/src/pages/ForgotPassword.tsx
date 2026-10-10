import { type FormEvent, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BrandPanel } from '../components/BrandPanel';
import { Icon } from '../components/Icon';
import { PasswordInput } from '../components/PasswordInput';
import { ApiError, api } from '../services/api';

type Step = 'ask' | 'reset' | 'done';

/** Forgot password: a code is texted to the verified phone on the account, then a new password is chosen. */
export default function ForgotPassword() {
  const [params] = useSearchParams();
  const role = params.get('role');
  const back = role === 'advocate' || role === 'petitioner' || role === 'admin' ? `/login/${role}` : '/';
  const [step, setStep] = useState<Step>('ask');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const [development, setDevelopment] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const reply = await api.post<{ detail: string; delivery?: string }>('/auth/password/forgot', { identifier: identifier.trim() });
      setNote(reply.detail);
      setDevelopment(reply.delivery === 'development');
      setStep('reset');
    } catch (e) {
      setError(e instanceof ApiError && e.status === 429 ? 'Too many tries. Please wait a while and try again.' : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function reset(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post('/auth/password/reset', { identifier: identifier.trim(), code, new_password: password });
      setStep('done');
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 400
          ? 'That code is not right, or it has expired. Check it or ask for a new one.'
          : e instanceof ApiError && e.status === 422
            ? 'Choose a password of at least 10 characters.'
            : 'Something went wrong. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="split" data-screen="forgot-password">
      <BrandPanel>
        <h1>MrCourt</h1>
        <p className="lead">Trusted legal guidance, grounded in Indian law.</p>
      </BrandPanel>
      <div className="panel">
        {step === 'ask' && (
          <form onSubmit={ask}>
            <Link to={back} className="back">
              <Icon name="back" />
              Back
            </Link>
            <h2>Forgot your password?</h2>
            <p className="sub">Enter your email or mobile number. We will text a code to the verified mobile number on your account.</p>
            <label className="field" htmlFor="forgot-id">
              Email or phone
              <input id="forgot-id" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required />
            </label>
            {error && (
              <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
                {error}
              </p>
            )}
            <button className="btn" type="submit" disabled={busy || !identifier.trim()}>
              Send code
            </button>
          </form>
        )}
        {step === 'reset' && (
          <form onSubmit={reset}>
            <button type="button" className="back" onClick={() => setStep('ask')}>
              <Icon name="back" />
              Back
            </button>
            <h2>Choose a new password</h2>
            <p className="fine" role="status">
              {note}
            </p>
            {development && (
              <p className="fine" role="note">
                No text-message service is set up, so nothing was really sent. In development, read the code on the{' '}
                <Link to="/dev/messages" target="_blank" rel="noreferrer">
                  Development messages
                </Link>{' '}
                page.
              </p>
            )}
            <label className="field" htmlFor="reset-code">
              6-digit code
              <input
                id="reset-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                required
              />
            </label>
            <PasswordInput
              id="new-password"
              label="New password (at least 10 characters)"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              minLength={10}
            />
            {error && (
              <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
                {error}
              </p>
            )}
            <button className="btn" type="submit" disabled={busy || code.length !== 6}>
              Change password
            </button>
            <p className="fine" style={{ margin: 0 }}>
              <button type="button" className="back" onClick={() => void ask()} disabled={busy}>
                Send a new code
              </button>
            </p>
          </form>
        )}
        {step === 'done' && (
          <div>
            <h2>Password changed</h2>
            <p className="sub" role="status">
              Your password has been changed and you have been signed out everywhere. Please sign in with the new one.
            </p>
            <Link to={back} className="btn">
              Go to sign in
            </Link>
          </div>
        )}
      </div>
    </section>
  );
}
