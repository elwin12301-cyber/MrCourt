import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { initials } from '../components/AppShell';
import { ContactCardForm } from '../components/ContactCardForm';
import { PhoneCodeStep } from '../components/PhoneCodeStep';
import { DeactivateDialog } from '../components/DeactivateDialog';
import { Button, Chip } from '../components/ui';
import { downloadMyData, errorText, useUpdatePhone, useUpdateSettings } from '../services/account';
import { ME_KEY, type Settings as UserSettings, useMe, useSignOut } from '../services/auth';
import { type Theme, setTheme } from '../services/theme';


export default function Settings() {
  const { data: me } = useMe();
  const signOut = useSignOut();
  const navigate = useNavigate();
  const update = useUpdateSettings();
  const updatePhone = useUpdatePhone();
  const [phone, setPhone] = useState<string | null>(null);
  const [phoneNote, setPhoneNote] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const client = useQueryClient();
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  if (!me) return null;
  const settings: UserSettings = me.settings;

  function change(patch: Partial<UserSettings>) {
    update.mutate(patch);
  }

  async function leave() {
    await signOut();
    navigate('/', { replace: true });
  }

  return (
    <section className="view" id="settings" data-view="settings">
      <div>
        <h1>Settings</h1>
        <p className="sub">Account, language and alerts</p>
      </div>
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
            <div className="avatar" style={{ width: 56, height: 56, fontSize: 18 }}>
              {initials(me.full_name)}
            </div>
            <div>
              <h2 style={{ fontSize: 20 }}>{me.full_name}</h2>
              {me.bar_registration_number && (
                <span style={{ color: 'var(--muted)', fontSize: 12 }}>
                  Bar registration · {me.bar_registration_number}
                </span>
              )}
            </div>
          </div>
          {me.verification_status === 'verified' && (
            <span>
              <Chip tone="ok">Bar Council verified</Chip>
            </span>
          )}
          {me.verification_status === 'pending' && (
            <span>
              <Chip tone="soon">Verification pending</Chip>
            </span>
          )}
          <Button variant="ghost" style={{ marginTop: 8 }} onClick={() => void leave()}>
            Sign out
          </Button>
        </div>

        <div className="card" style={{ padding: '8px 22px' }}>
          <div className="set">
            <b style={{ fontWeight: 500 }}>Language</b>
            <span>English</span>
          </div>
          <div className="set">
            <b style={{ fontWeight: 500 }} id="appearance-label">Appearance</b>
            <select
              aria-labelledby="appearance-label"
              value={settings.theme}
              onChange={(e) => {
                const theme = e.target.value as Theme;
                setTheme(theme);
                change({ theme });
              }}
            >
              <option value="system">Match my device</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
          {me.role !== 'admin' && (
            <>
              <div className="set">
                <b style={{ fontWeight: 500 }}>Text message reminders</b>
                <button
                  type="button"
                  className="toggle"
                  role="switch"
                  aria-checked={settings.whatsapp_reminders}
                  aria-label="Text message reminders"
                  onClick={() => change({ whatsapp_reminders: !settings.whatsapp_reminders })}
                />
              </div>
              <div className="set" style={{ alignItems: 'flex-start' }}>
                <b style={{ fontWeight: 500 }}>Reminder schedule</b>
                <span className="fine" style={{ margin: 0, textAlign: 'right' }}>
                  5 days before, 1 day before and on the day of each hearing
                </span>
              </div>
            </>
          )}
          <div className="set" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <label htmlFor="reminder-phone" style={{ fontWeight: 500 }}>
              Mobile number
            </label>
            <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                id="reminder-phone"
                type="tel"
                autoComplete="tel"
                value={phone ?? me.phone ?? ''}
                onChange={(e) => {
                  setPhone(e.target.value);
                  setPhoneNote(null);
                }}
                placeholder="+91…"
                style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--line)', background: 'var(--surface)', color: 'var(--ink)', font: 'inherit' }}
              />
              <Button
                small
                variant="ghost"
                disabled={updatePhone.isPending || phone === null}
                onClick={async () => {
                  try {
                    await updatePhone.mutateAsync(phone ?? '');
                    setPhone(null);
                    setPhoneNote('Saved. Verify the new number to use it for reminders and password resets.');
                  } catch (e) {
                    setPhoneNote(errorText(e, 'Could not save the number.'));
                  }
                }}
              >
                Save
              </Button>
              {me.phone && (
                <Chip tone={me.phone_verified ? 'ok' : 'soon'}>{me.phone_verified ? 'Verified' : 'Not verified'}</Chip>
              )}
              {me.phone && !me.phone_verified && phone === null && !verifying && (
                <Button small onClick={() => setVerifying(true)}>
                  Verify
                </Button>
              )}
            </span>
            <span className="fine" style={{ flexBasis: '100%' }} role="status">
              {phoneNote ??
                (me.phone_verified
                  ? 'Hearing reminders and password reset codes are texted to this number.'
                  : me.phone
                    ? 'Verify this number to get hearing reminders and to be able to reset your password.'
                    : 'Add a mobile number to get hearing reminders and to be able to reset your password.')}
            </span>
            {verifying && me.phone && !me.phone_verified && (
              <div style={{ flexBasis: '100%' }}>
                <PhoneCodeStep
                  phone={me.phone}
                  onVerified={() => {
                    setVerifying(false);
                    setPhoneNote('Your mobile number is verified.');
                    void client.invalidateQueries({ queryKey: ME_KEY });
                  }}
                  onSkip={() => setVerifying(false)}
                  skipLabel="Cancel"
                />
              </div>
            )}
          </div>
          <div className="set">
            <b style={{ fontWeight: 500 }}>Privacy &amp; data (DPDP)</b>
            <button
              type="button"
              className="back"
              aria-expanded={privacyOpen}
              onClick={() => setPrivacyOpen((v) => !v)}
              style={{ color: 'var(--gold-ink)', fontWeight: 600 }}
            >
              Manage
            </button>
          </div>
          {privacyOpen && (
            <div style={{ padding: '4px 4px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p className="fine">
                We keep only what we need to run your account. You can download everything we hold about
                you, or deactivate your account. Case records are kept when you deactivate.
              </p>
              <p className="fine">
                Your questions are kept in History, visible only to you, and are removed when you deactivate.
                When an AI service is set up, a question you ask (and, in Assistant mode, the case details it
                needs) is sent to that service to write the reply. For meaning-based search, the text of
                knowledge sources and your question are sent to Voyage AI. Voice input is handled by your
                browser by default and MrCourt never receives the audio; if you choose the speech service
                (Better for Tamil, or the Text Assistant), your voice is sent to Sarvam AI to be turned into
                text. MrCourt does not store audio. Your mobile number is used only to text you verification codes, password
                reset codes and hearing reminders, through the text-message service that is set up (Twilio).
              </p>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Button
                  small
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await downloadMyData();
                      setNotice('Your data has been downloaded.');
                    } catch {
                      setNotice('Could not download your data. Please try again.');
                    }
                  }}
                >
                  Download my data
                </Button>
                {me.role !== 'admin' && (
                  <Button small variant="ghost" onClick={() => setDeactivating(true)}>
                    Deactivate account
                  </Button>
                )}
              </div>
              {notice && (
                <p className="fine" role="status">
                  {notice}
                </p>
              )}
            </div>
          )}
          <div className="set">
            <b style={{ fontWeight: 500 }}>Help &amp; support</b>
            <span>Not available yet</span>
          </div>
        </div>
      </div>
      {me.role === 'advocate' && <ContactCardForm />}
      <DeactivateDialog open={deactivating} onClose={() => setDeactivating(false)} onDone={() => void leave()} />
    </section>
  );
}
