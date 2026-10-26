import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { signInAs } from './support/helpers';
import { fakeVoice, finishSpeech, say, spoken, turnOnVoice, voiceBar } from './support/voice';

/** US3: speak into text fields, hear answers read with their sources and disclaimer, scroll and close dialogs. */

const ADVOCATE = 'rohan.sharma@example.com';

async function start(page: Page, path: string) {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await page.goto(path);
  await expect(page.locator('main')).toBeVisible();
  await turnOnVoice(page);
}

test('dictate a question, send it, hear the answer read with its sources and disclaimer', async ({ page }) => {
  await start(page, '/ask');
  const box = page.getByLabel('Ask a legal question');
  await say(page, 'dictate');
  await expect(voiceBar(page)).toContainText('Click a text field first');

  await say(page, 'click ask a legal question');
  await expect(box).toBeFocused();
  await say(page, 'dictate');
  await expect(voiceBar(page)).toContainText('Dictating');
  await say(page, 'What is the punishment for cheque bounce under Section 138');
  await say(page, 'go to dashboard'); // while dictating a command is only words
  await expect(box).toHaveValue('What is the punishment for cheque bounce under Section 138 go to dashboard');
  await expect(page).toHaveURL(/\/ask/);
  await say(page, 'clear field');
  await expect(box).toHaveValue('');
  await say(page, 'What is the punishment for cheque bounce under Section 138');
  await say(page, 'stop dictating');
  await expect(voiceBar(page)).toContainText('Stopped dictating');

  await say(page, 'click send'); // a question to the assistant needs no confirmation
  await expect(page.locator('.card.a [data-voice-read], .card.a').last()).toContainText('Section 138');

  await say(page, 'read the answer');
  await expect(voiceBar(page)).toContainText('Reading the answer');
  const read = (await spoken(page)).at(-1) ?? '';
  expect(read).toContain('Section 138');
  expect(read).toMatch(/not legal advice/i);

  // While it speaks, only "stop" is heard; everything else is ignored, so it never hears itself.
  await say(page, 'go to dashboard');
  await expect(page).toHaveURL(/\/ask/);
  await say(page, 'stop reading');
  await expect(voiceBar(page)).toContainText('Stopped reading');
  await finishSpeech(page).catch(() => undefined);
  await say(page, 'go to dashboard');
  await expect(page).toHaveURL(/\/dashboard/);
});

test('dictate into a form field by naming it', async ({ page }) => {
  await start(page, '/settings');
  await say(page, 'dictate in mobile number');
  await expect(voiceBar(page)).toContainText('Dictating');
  await say(page, '+91 98765 43210');
  await expect(page.getByLabel('Mobile number')).toHaveValue('+91 98765 43210');
  await say(page, 'stop dictating');
  await expect(voiceBar(page)).toContainText('Stopped dictating');
});

test('scroll down, up, to the top and to the bottom', async ({ page }) => {
  await start(page, '/settings');
  await page.evaluate(() => {
    const tall = document.createElement('div');
    tall.style.height = '4000px';
    tall.textContent = 'Long page';
    document.querySelector('main')?.appendChild(tall);
  });
  const y = () => page.evaluate(() => Math.round(window.scrollY));
  expect(await y()).toBe(0);
  await say(page, 'scroll down');
  await expect.poll(y).toBeGreaterThan(100);
  const down = await y();
  await say(page, 'scroll down');
  await expect.poll(y).toBeGreaterThan(down);
  await say(page, 'scroll up');
  await expect.poll(y).toBeLessThan(await y() + 1);
  await say(page, 'go to bottom');
  await expect.poll(() => page.evaluate(() => Math.round(window.scrollY + window.innerHeight >= document.body.scrollHeight - 5 ? 1 : 0))).toBe(1);
  await say(page, 'go to top');
  await expect.poll(y).toBe(0);
});

test('"close dialog" closes a dialog without changing anything, and the help list can be closed by voice', async ({ page }) => {
  await start(page, '/settings');
  await page.getByRole('button', { name: 'Manage', exact: true }).click();
  await page.getByRole('button', { name: 'Deactivate account' }).click();
  const dialog = page.getByRole('dialog', { name: /Deactivate your account/ });
  await expect(dialog).toBeVisible();
  await say(page, 'close dialog');
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('switch', { name: 'Allow voice control' })).toHaveAttribute('aria-checked', 'true');

  await say(page, 'what can I say');
  const help = page.getByRole('dialog', { name: 'What can I say?' });
  await expect(help).toBeVisible();
  await expect(help).toContainText('On this screen');
  await say(page, 'close dialog');
  await expect(help).toBeHidden();
  await say(page, 'cancel');
  await expect(voiceBar(page)).toContainText('nothing to cancel');
});
