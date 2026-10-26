import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { signInAs } from './helpers';

/**
 * A driveable stand-in for the browser's speech recognition and speech output (feature 011).
 *
 *   say(page, 'go to dashboard')   a finished phrase, as if heard
 *   endTurn(page)                   the browser ending a turn (the app must start listening again)
 *   spoken(page)                    what the app has read aloud
 *
 * Modes: `works`, `denied` (microphone blocked), `missing` (no recognition at all), `language` (the chosen language
 * is not supported). Build on the pattern of tests/e2e/voice.spec.ts.
 */
export type FakeMode = 'works' | 'denied' | 'missing' | 'language';

export async function fakeVoice(page: Page, mode: FakeMode = 'works', options: { replies?: boolean; speechMs?: number } = {}) {
  await page.addInitScript(([m, replies, speechMs]) => {
    const w = window as unknown as Record<string, unknown>;
    // Spoken replies are off unless a test asks for them: the fake speech output only ends when a test says so.
    try {
      localStorage.setItem('mrcourt.voice.replies', replies ? '1' : '0');
    } catch {
      /* storage unavailable */
    }
    const log = { starts: 0, spoken: [] as string[], cancels: 0, langs: [] as string[], speechMs: speechMs as number };
    w.__voice = log;
    if (m === 'missing') {
      w.SpeechRecognition = undefined;
      w.webkitSpeechRecognition = undefined;
    } else {
      class Fake {
        lang = '';
        interimResults = false;
        continuous = false;
        onresult: ((e: unknown) => void) | null = null;
        onerror: ((e: { error: string }) => void) | null = null;
        onend: (() => void) | null = null;
        stopped = false;
        start() {
          log.starts += 1;
          log.langs.push(this.lang);
          (w as { __rec?: unknown }).__rec = this;
          if (m === 'denied' || m === 'language') {
            const error = m === 'denied' ? 'not-allowed' : 'language-not-supported';
            setTimeout(() => {
              this.onerror?.({ error });
              this.onend?.();
            }, 0);
          }
        }
        stop() {
          this.stopped = true;
          setTimeout(() => this.onend?.(), 0);
        }
        abort() {
          this.stopped = true;
        }
        say(text: string, confidence: number) {
          const result = Object.assign([{ transcript: text, confidence }], { isFinal: true });
          this.onresult?.({ resultIndex: 0, results: [result] });
        }
      }
      w.SpeechRecognition = Fake;
    }
    // Speech output: records what is read and keeps "speaking" until it is cancelled or finished.
    let speaking = false;
    let last: { onend: (() => void) | null } | null = null;
    w.SpeechSynthesisUtterance = class {
      text: string;
      lang = '';
      voice: unknown = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(text: string) {
        this.text = text;
      }
    };
    w.__finishSpeech = () => {
      speaking = false;
      last?.onend?.();
    };
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        get speaking() {
          return speaking;
        },
        getVoices: () => [],
        cancel() {
          log.cancels += 1;
          if (speaking) {
            speaking = false;
            const u = last as { onerror?: (() => void) | null } | null;
            setTimeout(() => u?.onerror?.(), 0); // a real browser reports a cancelled utterance
          }
        },
        speak(u: { text: string; onend: (() => void) | null }) {
          log.spoken.push(u.text);
          speaking = true;
          last = u;
          // A spoken reply ends by itself after a moment (a prompt or a reading ends only when a test says so).
          if (log.speechMs > 0) {
            setTimeout(() => {
              if (last === u) {
                speaking = false;
                u.onend?.();
              }
            }, log.speechMs);
          }
        },
      },
    });
  }, [mode, !!options.replies, options.speechMs ?? 0] as const);
}

export const say = (page: Page, phrase: string, confidence = 0.9) =>
  page.evaluate(
    ([p, c]) => (window as unknown as { __rec: { say: (t: string, c: number) => void } }).__rec.say(p as string, c as number),
    [phrase, confidence] as const,
  );

export const endTurn = (page: Page) =>
  page.evaluate(() => {
    const rec = (window as unknown as { __rec: { onend: (() => void) | null } }).__rec;
    rec.onend?.();
  });

/**
 * The app has finished speaking (a prompt or a reading). It set listening aside while it spoke, so this waits until it
 * is listening again, as the real browser would after the speech ends.
 */
export async function finishSpeech(page: Page) {
  const before = await recognitionStarts(page);
  await page.evaluate(() => (window as unknown as { __finishSpeech: () => void }).__finishSpeech());
  await page.waitForFunction((n) => (window as unknown as { __voice: { starts: number } }).__voice.starts > n, before, { timeout: 5000 });
}

export const spoken = (page: Page) =>
  page.evaluate(() => (window as unknown as { __voice: { spoken: string[] } }).__voice.spoken);

export const recognitionStarts = (page: Page) =>
  page.evaluate(() => (window as unknown as { __voice: { starts: number } }).__voice.starts);

/** Turns voice control on through the launcher and the notice, and waits until it is listening. */
export async function turnOnVoice(page: Page) {
  await page.getByRole('button', { name: 'Turn on voice control', exact: true }).click();
  const notice = page.getByRole('dialog', { name: 'Turn on voice control?' });
  if (await notice.isVisible().catch(() => false)) {
    await notice.getByRole('button', { name: 'Agree and turn on' }).click();
  }
  await expect(voiceBar(page).getByRole('status').first()).toContainText('Listening');
}

/** The status line and result line of the voice bar. */
export const voiceBar = (page: Page) => page.getByRole('region', { name: 'Voice control', exact: true });

let accounts = 0;

/**
 * A fresh client account, signed in, for tests that change voice settings: the two layouts and many tests run at the
 * same time, and shared accounts would change each other's settings.
 */
export async function freshAccount(page: Page): Promise<string> {
  const email = `voice-${Date.now()}-${process.pid}-${accounts++}@example.com`;
  const made = await page.request.post('/api/v1/auth/register', {
    data: { role: 'petitioner', full_name: 'Voice Tester', email, password: 'a-strong-password' },
  });
  expect(made.ok()).toBeTruthy();
  await page.context().clearCookies();
  await signInAs(page, email, 'a-strong-password', 'petitioner');
  await page.waitForURL(/\/dashboard/); // signed in and landed: a reload before this would stay on the sign-in page
  return email;
}
