import { useState } from 'react';
import { useUpdateSettings } from '../services/account';
import { useMe } from '../services/auth';
import { VOICE_CONTROL_LANGUAGES } from '../voice/lang';
import { VOICE_SHORTCUT, useVoice } from '../voice/voiceContext';
import { Button } from './ui';

/**
 * Settings → Voice control (FR-001, FR-030, FR-032): agree to or withdraw from voice control, the separate cloud
 * option, and the language. Changes are saved at once and announced.
 */
export function VoiceSettingsCard() {
  const { data: me } = useMe();
  const voice = useVoice();
  const update = useUpdateSettings();
  const [note, setNote] = useState('');
  if (!me) return null;
  const settings = me.settings;

  async function toggleAgreement() {
    if (settings.voice_consent) {
      await voice.withdraw();
      setNote('Voice control agreement withdrawn. The microphone is off.');
    } else {
      voice.start(); // shows the notice; "Agree and turn on" records the agreement
    }
  }

  function toggleCloud() {
    update.mutate(
      { voice_cloud_opt_in: !settings.voice_cloud_opt_in },
      { onSuccess: () => setNote(settings.voice_cloud_opt_in ? 'The cloud speech service is off.' : 'The cloud speech service is on.') },
    );
  }

  return (
    <section id="voice-settings" aria-label="Voice control settings">
      <div className="set" style={{ alignItems: 'flex-start' }}>
        <span style={{ maxWidth: 440 }}>
          <b style={{ fontWeight: 500, display: 'block', color: 'var(--ink)' }}>
            Voice control
          </b>
          <small className="fine">
            Use MrCourt by speaking, for example “go to dashboard”. Start or stop it with the microphone button or{' '}
            {VOICE_SHORTCUT.label}. The mouse and keyboard always keep working.
          </small>
        </span>
        <button
          type="button"
          className="toggle"
          role="switch"
          aria-checked={settings.voice_consent}
          aria-label="Allow voice control"
          onClick={() => void toggleAgreement()}
        />
      </div>
      <div className="set">
        <b style={{ fontWeight: 500 }} id="voice-language-label">Voice language</b>
        <select
          aria-labelledby="voice-language-label"
          value={voice.language}
          onChange={(e) => {
            voice.setLanguage(e.target.value);
            setNote('Voice language saved.');
          }}
        >
          {VOICE_CONTROL_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>
      <div className="set" style={{ alignItems: 'flex-start' }}>
        <span style={{ maxWidth: 440 }}>
          <b style={{ fontWeight: 500, display: 'block', color: 'var(--ink)' }}>Cloud speech service</b>
          <small className="fine">
            For a language your browser cannot recognise, send short phrases to MrCourt’s speech service. They are not
            stored. Off by default; needs your agreement above.
          </small>
        </span>
        <button
          type="button"
          className="toggle"
          role="switch"
          aria-checked={settings.voice_cloud_opt_in}
          aria-label="Use the cloud speech service for languages my browser cannot recognise"
          disabled={!settings.voice_consent || update.isPending}
          onClick={toggleCloud}
        />
      </div>
      <div className="set">
        <b style={{ fontWeight: 500 }}>Commands</b>
        <Button small variant="ghost" onClick={voice.openHelp}>
          What can I say?
        </Button>
      </div>
      <p className="fine" role="status" aria-live="polite" style={{ minHeight: 18, margin: '4px 0 10px' }}>
        {note}
      </p>
    </section>
  );
}
