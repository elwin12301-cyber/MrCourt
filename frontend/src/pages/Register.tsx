import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { BrandPanel } from '../components/BrandPanel';
import { Icon } from '../components/Icon';
import { PasswordInput } from '../components/PasswordInput';
import { PhoneCodeStep } from '../components/PhoneCodeStep';
import { ApiError, api } from '../services/api';
import { ME_KEY } from '../services/auth';

type Role = 'advocate' | 'petitioner';
const isRole = (value: string | undefined): value is Role => value === 'advocate' || value === 'petitioner';

const COPY = {
  advocate: {
    label: 'Advocate sign up',
    sub: 'Informational guidance only. Not legal advice.',
  },
  petitioner: {
    label: 'Petitioner sign up',
    sub: 'Your lawyer invites you to your case. Use the email or phone number they have for you.',
  },
} as const;

function RegisterForm({ initialRole }: { initialRole: Role }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [role, setRole] = useState<Role>(initialRole);
  const copy = COPY[role];
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [bar, setBar] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!phone.trim()) {
      setError('Enter your mobile number. We text a code to it.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post('/auth/register', {
        role,
        username: username.trim(),
        full_name: fullName,
        email: email.trim(),
        phone: phone.trim() || null,
        password,
        bar_registration_number: role === 'advocate' && bar.trim() ? bar.trim() : null,
      });
      await client.invalidateQueries({ queryKey: ME_KEY });
      setCreated(true); // next: check the phone number with a texted code
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    const done = () => {
      void client.invalidateQueries({ queryKey: ME_KEY });
      navigate('/dashboard', { replace: true });
    };
    return (
      <section className="split" data-screen={`register-${role}-verify`}>
        <BrandPanel>
          <h1>MrCourt</h1>
          <p className="lead">One more step: confirm your mobile number.</p>
        </BrandPanel>
        <div className="panel">
          <div className="eyebrow">{copy.label}</div>
          <h2>Verify your mobile number</h2>
          <p className="sub">
            Your account is ready. Confirm your number to get hearing reminders by text message and to be able to reset
            your password.
          </p>
          <PhoneCodeStep phone={phone.replace(/[\s-]/g, '')} onVerified={done} onSkip={done} />
        </div>
      </section>
    );
  }

  return (
    <section className="split" data-screen={`register-${role}`}>
      <BrandPanel>
        <h1>MrCourt</h1>
        <p className="lead">
          {role === 'advocate'
            ? 'Trusted legal guidance, grounded in Indian law.'
            : 'Know where your case stands, and who is handling it.'}
        </p>
      </BrandPanel>
      <div className="panel">
        <form onSubmit={submit}>
          <Link to={`/login/${role}`} className="back">
            <Icon name="back" />
            Back
          </Link>
          <div className="eyebrow">{copy.label}</div>
          <h2>Create your account</h2>
          <p className="sub">{copy.sub}</p>
          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <legend>I am registering as</legend>
            <div style={{ display: 'flex', gap: 16 }}>
              {(['advocate', 'petitioner'] as const).map((value) => (
                <label key={value} htmlFor={`role-${value}`} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    id={`role-${value}`}
                    type="radio"
                    name="role"
                    value={value}
                    checked={role === value}
                    onChange={() => setRole(value)}
                  />
                  {value === 'advocate' ? 'Advocate' : 'Petitioner'}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="field" htmlFor="username">
            Username
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              minLength={3}
              maxLength={30}
              pattern="[A-Za-z][A-Za-z0-9._\-]{2,29}"
              title="3 to 30 characters: letters, numbers, dots, dashes or underscores. Start with a letter."
              aria-describedby="username-help"
            />
          </label>
          <p id="username-help" className="fine" style={{ margin: 0 }}>
            3 to 30 letters, numbers, dots, dashes or underscores. You can sign in with it.
          </p>
          <label className="field" htmlFor="name">
            Full name
            <input id="name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label className="field" htmlFor="email">
            Email
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>
          <label className="field" htmlFor="phone">
            Mobile number
            <input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="tel"
              placeholder="+91 98765 43210"
              required
            />
          </label>
          <PasswordInput
            id="password"
            label="Password (at least 10 characters)"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            minLength={10}
          />
          {role === 'advocate' && (
            <label className="field" htmlFor="bar">
              Bar Council registration number
              <input id="bar" value={bar} onChange={(e) => setBar(e.target.value)} placeholder="e.g. D/1234/2015" />
            </label>
          )}
          {error && (
            <p className="fine" role="alert" style={{ color: 'var(--gold-ink)', fontWeight: 600 }}>
              {error}
            </p>
          )}
          <button className="btn" type="submit" disabled={busy}>
            Create account
          </button>
          <p className="fine">
            We collect only what we need to run your account. See Privacy and data in Settings.
          </p>
        </form>
      </div>
    </section>
  );
}

/** One sign-up page: `/register` (older links carry `?role=`) or `/register/advocate|petitioner` to preselect. */
export default function Register() {
  const { role } = useParams();
  const [params] = useSearchParams();
  if (role !== undefined && !isRole(role)) return <Navigate to="/" replace />;
  const initial: Role = role ?? (params.get('role') === 'petitioner' ? 'petitioner' : 'advocate');
  return <RegisterForm initialRole={initial} />;
}
