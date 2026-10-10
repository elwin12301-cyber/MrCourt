import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { BrandPanel } from '../components/BrandPanel';
import { Icon } from '../components/Icon';
import { PasswordInput } from '../components/PasswordInput';
import { Button } from '../components/ui';
import { ApiError, api } from '../services/api';
import { ME_KEY, type Me } from '../services/auth';

type Step = 'password' | 'otp';
type Role = 'advocate' | 'petitioner' | 'admin';

const isRole = (value: string | undefined): value is Role =>
  value === 'advocate' || value === 'petitioner' || value === 'admin';

/** `/login` on its own goes to the matching sign-in (older links carry `?role=`). */
export function LoginRedirect() {
  const [params] = useSearchParams();
  const role = params.get('role') === 'petitioner' ? 'petitioner' : 'advocate';
  return <Navigate to={`/login/${role}`} replace />;
}

const COPY = {
  advocate: {
    label: 'Advocate sign in',
    sub: 'Sign in to manage your cases, drafts and clients',
    other: { to: '/login/petitioner', text: 'Petitioner? Sign in here' },
  },
  petitioner: {
    label: 'Petitioner sign in',
    sub: 'Sign in to see where your case stands',
    other: { to: '/login/advocate', text: 'Advocate? Sign in here' },
  },
  admin: {
    label: 'Administrator sign in',
    sub: 'Sign in to look after accounts and cases',
    other: { to: '/', text: 'Not an administrator? Go back' },
  },
} as const;

const ROLE_WORDS = {
  advocate: { with: 'an Advocate', page: 'Advocate' },
  petitioner: { with: 'a Petitioner', page: 'Petitioner' },
  admin: { with: 'an Administrator', page: 'Administrator' },
} as const;

function LoginBrand({ role }: { role: Role }) {
  if (role === 'advocate') {
    // Identical to the prototype's sign-in panel.
    return (
      <BrandPanel>
        <p className="lead">“The law is reason, free from passion.”</p>
        <p style={{ color: 'var(--sand)', margin: 0 }}>Aristotle</p>
      </BrandPanel>
    );
  }
  if (role === 'admin') {
    return (
      <BrandPanel>
        <p className="lead">Looking after the people and the cases on MrCourt.</p>
        <ul>
          <li><Icon name="check" />Manage advocate and client accounts</li>
          <li><Icon name="check" />See every case, read-only</li>
          <li><Icon name="check" />Everything you open or change is recorded</li>
        </ul>
      </BrandPanel>
    );
  }
  return (
    <BrandPanel>
      <p className="lead">Know where your case stands, and who is handling it.</p>
      <ul>
        <li><Icon name="check" />See your next hearing and what happens at it</li>
        <li><Icon name="check" />Ask your lawyer a question inside MrCourt</li>
        <li><Icon name="check" />Only you and your lawyer can see your case</li>
      </ul>
    </BrandPanel>
  );
}

function LoginForm({ role }: { role: Role }) {
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const copy = COPY[role];
  const destination = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<Step>('password');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function finish() {
    // Each person sees only their own screens. An account of the other kind is signed out again
    // with an explanation, instead of opening the other role's screens.
    const me = await api.get<Me>('/me');
    if (me.role !== role) {
      await api.post('/auth/logout');
      setError(
        `This account is registered as ${ROLE_WORDS[me.role].with}, not ${ROLE_WORDS[role].with}. Please use the ${ROLE_WORDS[me.role].page} sign in.`,
      );
      return;
    }
    await client.invalidateQueries({ queryKey: ME_KEY });
    navigate(destination, { replace: true });
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      if (step === 'otp') {
        await api.post('/auth/otp/verify', { identifier, code });
      } else {
        await api.post('/auth/login', { identifier, password });
      }
      await finish();
    });
  }

  function startOtp() {
    if (!identifier.trim()) {
      setError('Enter your email or phone first.');
      return;
    }
    void run(async () => {
      await api.post('/auth/otp/request', { identifier });
      setStep('otp');
      setMessage('If the account exists, we have sent a 6-digit code.');
    });
  }

  return (
    <section className="split" id="login" data-screen={`login-${role}`}>
      <LoginBrand role={role} />
      <div className="panel">
        <form id="loginForm" onSubmit={submit}>
          <Link to="/" className="back">
            <Icon name="back" />
            Back
          </Link>
          <div className="eyebrow">{copy.label}</div>
          <h2>Welcome back</h2>
          <p className="sub">{copy.sub}</p>
          <label className="field" htmlFor="em">
            Email or phone (or username)
            <input
              id="em"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          {step === 'password' ? (
            <PasswordInput
              id="pw"
              label="Password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
            />
          ) : (
            <label className="field" htmlFor="otp">
              6-digit code
              <input
                id="otp"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="one-time-code"
                required
              />
            </label>
          )}
          {step === 'password' && (
            <p className="fine" style={{ margin: 0 }}>
              <Link to={`/forgot-password?role=${role}`}>Forgot password?</Link>
            </p>
          )}
          {message && (
            <p className="fine" role="status">
              {message}
            </p>
          )}
          {error && (
            <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
              {error}
            </p>
          )}
          <button className="btn" type="submit" disabled={busy}>
            {step === 'otp' ? 'Verify code' : 'Sign in'}
          </button>
          <div className="or">or</div>
          {step === 'password' ? (
            <Button variant="ghost" onClick={startOtp} disabled={busy}>
              Continue with OTP
            </Button>
          ) : (
            <Button
              variant="ghost"
              onClick={() => {
                setStep('password');
                setMessage(null);
                setError(null);
              }}
            >
              Use password instead
            </Button>
          )}
          {role !== 'admin' && (
            <p className="fine" style={{ textAlign: 'center' }}>
              New to MrCourt? <Link to={`/register/${role}`}>Create an account</Link>
            </p>
          )}
          <p className="fine" style={{ textAlign: 'center', margin: 0 }}>
            <Link to={copy.other.to}>{copy.other.text}</Link>
          </p>
        </form>
      </div>
    </section>
  );
}

export default function Login() {
  const { role } = useParams();
  if (!isRole(role)) return <Navigate to="/" replace />;
  // Remount when switching between the two sign-ins so nothing typed carries over.
  return <LoginForm key={role} role={role} />;
}
