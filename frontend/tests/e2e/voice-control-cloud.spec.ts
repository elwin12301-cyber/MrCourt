import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { fakeVoice, freshAccount, voiceBar } from './support/voice';

/**
 * The opt-in cloud option (FR-032): for a language the browser cannot recognise, and only if the person agreed and
 * chose it, each short phrase is sent to the speech service and nothing else is. A fake microphone that the test can
 * "speak" into replaces the real one, and the speech endpoint is stubbed.
 */

async function fakeMicrophone(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    const state = { opened: 0, gain: null as GainNode | null };
    w.__mic = state;
    // Speaks once the app has opened the microphone (it takes a moment after "Listening" is shown).
    w.__speak = (ms: number) => {
      const timer = setInterval(() => {
        if (!state.gain) return;
        clearInterval(timer);
        state.gain.gain.value = 0.5;
        setTimeout(() => {
          if (state.gain) state.gain.gain.value = 0;
        }, ms);
      }, 50);
    };
    navigator.mediaDevices.getUserMedia = async () => {
      state.opened += 1;
      const context = new AudioContext();
      await context.resume();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      gain.gain.value = 0;
      const destination = context.createMediaStreamDestination();
      oscillator.connect(gain);
      gain.connect(destination);
      oscillator.start();
      state.gain = gain;
      return destination.stream;
    };
  });
}

const speak = (page: Page, ms = 1600) => page.evaluate((n) => (window as unknown as { __speak: (m: number) => void }).__speak(n), ms);
const opened = (page: Page) => page.evaluate(() => (window as unknown as { __mic: { opened: number } }).__mic.opened);

async function chooseCloud(page: Page, on: boolean) {
  const patched = await page.request.patch('/api/v1/me/settings', { data: { voice_consent: true, voice_cloud_opt_in: on } });
  expect(patched.ok()).toBeTruthy();
}

test('with the cloud option, a language the browser cannot recognise sends one short phrase at a time', async ({ page }) => {
  test.slow(); // real audio processing: slow when several browsers share the machine
  const requests: { type: string | undefined; size: number }[] = [];
  await page.route('**/api/v1/speech/transcribe', async (route) => {
    requests.push({ type: route.request().headers()['content-type'], size: route.request().postDataBuffer()?.length ?? 0 });
    await route.fulfill({ json: { text: requests.length === 1 ? 'open cases' : 'go to dashboard' } });
  });
  await fakeVoice(page, 'language'); // the browser: "language not supported"
  await fakeMicrophone(page);
  await freshAccount(page);
  await chooseCloud(page, true);
  await page.goto('/dashboard');
  expect(requests).toHaveLength(0); // nothing is sent while voice control is off

  await page.getByRole('button', { name: 'Turn on voice control', exact: true }).click();
  await expect(voiceBar(page)).toContainText('Listening');
  expect(requests).toHaveLength(0); // listening alone sends nothing
  await expect.poll(() => opened(page)).toBeGreaterThan(0);

  // A slow machine can lose the start of a phrase, so speaking is repeated until the answer arrives.
  await expect(async () => {
    await speak(page);
    await expect(page).toHaveURL(/\/cases$/, { timeout: 7000 });
  }).toPass({ timeout: 40_000 });
  await expect(voiceBar(page)).toContainText('Heard: “open cases”');
  expect(requests.length).toBeGreaterThanOrEqual(1);
  expect(requests[0].type).toContain('multipart/form-data');
  expect(requests[0].size).toBeGreaterThan(1000); // one short phrase of audio, not a stream
  expect(requests[0].size).toBeLessThan(400_000);

  await expect(async () => {
    await speak(page);
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 7000 });
  }).toPass({ timeout: 40_000 });
  for (const r of requests) expect(r.size).toBeLessThan(400_000); // every request is one short phrase

  // Stopping releases the microphone: no more phrases are sent.
  await voiceBar(page).getByRole('button', { name: 'Stop' }).click();
  await page.waitForTimeout(800);
  const after = requests.length;
  await speak(page).catch(() => undefined);
  await page.waitForTimeout(2500);
  expect(requests).toHaveLength(after);
});

test('the dashboard says when the cloud speech service is in use', async ({ page }) => {
  await page.route('**/api/v1/speech/transcribe', (route) => route.fulfill({ json: { text: '' } }));
  await fakeVoice(page, 'language');
  await fakeMicrophone(page);
  await freshAccount(page);
  await chooseCloud(page, true);
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Microphone: turn on voice control' }).click();
  await expect(page.getByText('Using the cloud speech service: short phrases are sent')).toBeVisible();
});

test('without the cloud option that language is not used, and nothing is sent or recorded', async ({ page }) => {
  let sent = 0;
  await page.route('**/api/v1/speech/transcribe', (route) => {
    sent += 1;
    return route.fulfill({ json: { text: 'open cases' } });
  });
  await fakeVoice(page, 'language');
  await fakeMicrophone(page);
  await freshAccount(page);
  await chooseCloud(page, false);
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Turn on voice control', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: "can't listen in that language" }).first()).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { __mic: { opened: number } }).__mic.opened)).toBe(0);
  await page.waitForTimeout(500);
  expect(sent).toBe(0);
});

test('a busy speech service pauses voice control with a plain message', async ({ page }) => {
  test.slow();
  await page.route('**/api/v1/speech/transcribe', (route) => route.fulfill({ status: 429, json: { detail: 'Too many requests' } }));
  await fakeVoice(page, 'language');
  await fakeMicrophone(page);
  await freshAccount(page);
  await chooseCloud(page, true);
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Turn on voice control', exact: true }).click();
  await expect(voiceBar(page)).toContainText('Listening');
  await expect.poll(() => opened(page)).toBeGreaterThan(0);
  await expect(async () => {
    await speak(page);
    await expect(page.getByRole('alert').filter({ hasText: 'busy, so voice control is paused for a minute' })).toBeVisible({ timeout: 7000 });
  }).toPass({ timeout: 40_000 });
  await expect(page).toHaveURL(/\/dashboard/);
});

test('the cloud option can only be chosen after agreeing to voice control', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page);
  const refused = await page.request.patch('/api/v1/me/settings', { data: { voice_consent: false, voice_cloud_opt_in: true } });
  expect(refused.status()).toBe(422);
  await page.goto('/settings');
  await expect(page.getByRole('switch', { name: /cloud speech service/ })).toBeVisible();
});
