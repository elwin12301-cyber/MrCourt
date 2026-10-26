import { expect, test } from './support/test';
import { signInAs } from './support/helpers';
import { fakeVoice, say, spoken, turnOnVoice, voiceBar, recognitionStarts } from './support/voice';

/** The app says what it did ("Opened Overview"), and a menu name said on its own works. */

test('a menu name on its own opens it, and the app says so aloud', async ({ page }) => {
  await fakeVoice(page, 'works', { replies: true, speechMs: 60 });
  await signInAs(page, 'admin@example.com');
  await turnOnVoice(page);

  await expect(async () => {
    await say(page, 'advocates');
    await expect(page).toHaveURL(/\/admin\/advocates/, { timeout: 3000 });
  }).toPass({ timeout: 20_000 });
  await expect.poll(() => spoken(page)).toContain('Opened “Advocates”.');

  // It listens again once it has spoken (the recogniser is set aside while the app talks).
  await expect.poll(() => recognitionStarts(page), { timeout: 5000 }).toBeGreaterThan(1);
  await expect(voiceBar(page)).toContainText('Listening');
  // (said again if a slow machine was still speaking the last reply)
  await expect(async () => {
    await say(page, 'overview');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 3000 });
  }).toPass({ timeout: 20_000 });
  await expect.poll(() => spoken(page)).toContain('Opened “Overview”.');
});

test('a wrong name is answered aloud with what to say instead', async ({ page }) => {
  await fakeVoice(page, 'works', { replies: true, speechMs: 60 });
  await signInAs(page, 'admin@example.com');
  await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Advocates' })).toBeVisible(); // the menu is on screen before anything is said
  await turnOnVoice(page);
  await say(page, 'open the unicorn page');
  await expect.poll(async () => (await spoken(page)).join(' ')).toContain('Try saying “go to');
  await expect(voiceBar(page)).toContainText('Try saying');
});

test('the Replies button turns the spoken replies off and on', async ({ page }) => {
  await fakeVoice(page, 'works', { replies: true, speechMs: 60 });
  await signInAs(page, 'admin@example.com');
  await turnOnVoice(page);
  const button = voiceBar(page).getByRole('button', { name: 'Replies' });
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'false');
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  await page.waitForTimeout(400);
  expect(await spoken(page)).toEqual([]);
  await voiceBar(page).getByRole('button', { name: 'Replies' }).click();
  await say(page, 'go to dashboard');
  await expect.poll(() => spoken(page)).toContain('Opened “Overview”.');
});

test('with replies off, nothing is read out (the default for the other voice tests)', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, 'admin@example.com');
  await turnOnVoice(page);
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  expect(await spoken(page)).toEqual([]);
});
