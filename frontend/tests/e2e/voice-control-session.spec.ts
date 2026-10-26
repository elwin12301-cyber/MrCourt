import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { signInAs } from './support/helpers';
import { endTurn, fakeVoice, freshAccount, recognitionStarts, say, turnOnVoice, voiceBar } from './support/voice';

/** US5: opt-in with consent, continuous listening until stopped, and a plain way to turn it off. */

const ADVOCATE = 'rohan.sharma@example.com';

async function signedIn(page: Page, email = ADVOCATE) {
  await fakeVoice(page);
  await signInAs(page, email);
}

const launcher = (page: Page) => page.getByRole('button', { name: 'Turn on voice control', exact: true });

test('first use shows the notice, and nothing listens until the person agrees', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page); // a person who has never agreed
  await launcher(page).click();
  const notice = page.getByRole('dialog', { name: 'Turn on voice control?' });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText('does not receive, record or store');
  await expect(notice).toContainText('stop listening');
  expect(await recognitionStarts(page)).toBe(0);

  await notice.getByRole('button', { name: 'Not now' }).click();
  await expect(notice).toBeHidden();
  expect(await recognitionStarts(page)).toBe(0);
  await expect(launcher(page)).toBeVisible();

  await launcher(page).click();
  await notice.getByRole('button', { name: 'Agree and turn on' }).click();
  await expect(voiceBar(page)).toContainText('Listening');
  expect(await recognitionStarts(page)).toBeGreaterThan(0);

  // The agreement is kept with the person's settings: no notice the next time, on this or another device.
  await page.reload();
  await launcher(page).click();
  await expect(page.getByRole('dialog', { name: 'Turn on voice control?' })).toBeHidden();
  await expect(voiceBar(page)).toContainText('Listening');
});

test('after one tap it keeps listening through many commands, pauses and screen changes, until stopped', async ({ page }) => {
  await signedIn(page);
  await turnOnVoice(page);
  const phrases = [
    'open cases', 'go to ask mrcourt', 'open the history tab', 'go to drafts', 'go to settings', 'go to dashboard',
    'open cases', 'go back', 'go to settings', 'go to dashboard',
  ];
  for (const phrase of phrases) {
    const before = await recognitionStarts(page);
    await say(page, phrase);
    await expect(voiceBar(page)).toContainText(`Heard: “${phrase}”`);
    await endTurn(page); // the browser ends its turn after a silence: the app starts it again
    await expect.poll(() => recognitionStarts(page), { timeout: 5000 }).toBeGreaterThan(before);
  }
  await expect(voiceBar(page)).toContainText('Listening');
  await expect(page).toHaveURL(/\/dashboard/);

  await say(page, 'stop listening');
  await expect(launcher(page)).toBeVisible();
  await expect(voiceBar(page)).toHaveCount(0);
  const stopped = await recognitionStarts(page);
  await endTurn(page).catch(() => undefined);
  await page.waitForTimeout(1200);
  expect(await recognitionStarts(page)).toBe(stopped); // never starts again by itself
});

test('the button and the keyboard shortcut also start and stop it', async ({ page }) => {
  await signedIn(page);
  await turnOnVoice(page);
  await voiceBar(page).getByRole('button', { name: /^Voice control is on/ }).click();
  await expect(launcher(page)).toBeVisible();

  await page.keyboard.press('Alt+Shift+V');
  await expect(voiceBar(page)).toContainText('Listening');
  await page.keyboard.press('Alt+Shift+V');
  await expect(launcher(page)).toBeVisible();

  await turnOnVoice(page);
  await voiceBar(page).getByRole('button', { name: 'Stop' }).click();
  await expect(launcher(page)).toBeVisible();
});

test('a blocked microphone and a browser with no speech support are explained, and the mouse and keyboard still work', async ({ page }) => {
  await fakeVoice(page, 'denied');
  await freshAccount(page);
  await launcher(page).click();
  await page.getByRole('dialog', { name: 'Turn on voice control?' }).getByRole('button', { name: 'Agree and turn on' }).click().catch(() => undefined);
  await expect(page.getByRole('status').filter({ hasText: 'microphone is blocked' }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Cases' }).click();
  await expect(page).toHaveURL(/\/cases$/);
});

test('a browser with no speech recognition says so and everything still works by mouse and keyboard', async ({ page }) => {
  await fakeVoice(page, 'missing');
  await signInAs(page, ADVOCATE);
  await launcher(page).click();
  await expect(page.getByRole('status').filter({ hasText: "isn't available in this browser" }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page).toHaveURL(/\/settings/);
});

test('"speak Tamil" changes the listening language', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page);
  await turnOnVoice(page);
  await say(page, 'speak Tamil');
  await expect(voiceBar(page)).toContainText('Now listening in Tamil');
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __voice: { langs: string[] } }).__voice.langs.at(-1)), { timeout: 5000 })
    .toBe('ta-IN');
  await say(page, 'dashboard ku po'); // and the mixed phrases keep working
  await expect(page).toHaveURL(/\/dashboard/);
});

test('it pauses while the tab is hidden and carries on when it is shown', async ({ page }) => {
  await signedIn(page);
  await turnOnVoice(page);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(voiceBar(page)).toContainText('Paused');
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(voiceBar(page)).toContainText('Listening');
});

test('withdrawing the agreement in Settings stops it and brings the notice back', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page);
  await turnOnVoice(page);
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  const agree = page.getByRole('switch', { name: 'Allow voice control' });
  await expect(agree).toHaveAttribute('aria-checked', 'true');
  await agree.click();
  await expect(agree).toHaveAttribute('aria-checked', 'false');
  await expect(launcher(page)).toBeVisible();
  const me = await (await page.request.get('/api/v1/me')).json();
  expect(me.settings.voice_consent).toBe(false);
  expect(me.settings.voice_cloud_opt_in).toBe(false);

  await launcher(page).click();
  await expect(page.getByRole('dialog', { name: 'Turn on voice control?' })).toBeVisible();
  await page.getByRole('button', { name: 'Not now' }).click();
  // leave it as it was for the other tests
  await page.getByRole('switch', { name: 'Allow voice control' }).click();
  await page.getByRole('dialog', { name: 'Turn on voice control?' }).getByRole('button', { name: 'Agree and turn on' }).click();
  await expect(voiceBar(page)).toContainText('Listening');
});

test('what is said is not kept: not in storage and not sent anywhere', async ({ page }) => {
  const sent: string[] = [];
  page.on('request', (request) => {
    const body = request.postData();
    if (body) sent.push(body);
    sent.push(request.url());
  });
  await signedIn(page);
  await turnOnVoice(page);
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  await say(page, 'open the unicorn page');
  await voiceBar(page).getByRole('button', { name: 'Stop' }).click();
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
  for (const phrase of ['go to settings', 'unicorn']) {
    expect(stored).not.toContain(phrase);
    expect(sent.join('\n')).not.toContain(phrase.replace(/ /g, '%20'));
    expect(sent.join('\n')).not.toContain(phrase);
  }
});
