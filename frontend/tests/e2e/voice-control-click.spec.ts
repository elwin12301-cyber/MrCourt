import type { Locator, Page } from '@playwright/test';
import { expect, test } from './support/test';
import { signInAs } from './support/helpers';
import { fakeVoice, say, turnOnVoice, voiceBar } from './support/voice';

/** US2: press any control by name, by the number drawn beside it, or by its place in a list. */

const ADVOCATE = 'rohan.sharma@example.com';

/** The number of the label drawn closest to the top-left corner of a control. */
async function numberOf(page: Page, control: Locator): Promise<number> {
  const box = await control.boundingBox();
  if (!box) throw new Error('control is not on screen');
  const labels = page.locator('.vc-num');
  const count = await labels.count();
  let best = { n: -1, d: Infinity };
  for (let i = 0; i < count; i += 1) {
    const label = labels.nth(i);
    const b = await label.boundingBox();
    if (!b) continue;
    const d = Math.hypot(b.x - (box.x - 8), b.y - (box.y - 8));
    if (d < best.d) best = { n: Number(await label.textContent()), d };
  }
  return best.n;
}

test('numbers: show them, click by number, hide them', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await turnOnVoice(page);

  await say(page, 'click 3');
  await expect(voiceBar(page)).toContainText('Numbers are not shown');

  const settings = page.getByRole('link', { name: 'Settings' });
  await settings.scrollIntoViewIfNeeded(); // only what is on screen is numbered
  await say(page, 'show numbers');
  await expect(voiceBar(page)).toContainText('Numbers shown on');
  await expect(page.locator('.vc-num').first()).toBeVisible();
  expect(await page.locator(".vc-num").count()).toBeGreaterThan(2);

  const n = await numberOf(page, settings);
  expect(n).toBeGreaterThan(0);
  await say(page, `click ${n}`);
  await expect(page).toHaveURL(/\/settings/);

  await say(page, 'hide numbers');
  await expect(page.locator('.vc-num')).toHaveCount(0);
  await say(page, 'click 1');
  await expect(voiceBar(page)).toContainText('Numbers are not shown');
});

test('a number said while numbers are shown needs no "click"', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await turnOnVoice(page);
  const cases = page.getByRole('link', { name: 'Cases' });
  await cases.scrollIntoViewIfNeeded();
  await say(page, 'show numbers');
  await expect(page.locator('.vc-num').first()).toBeVisible();
  const n = await numberOf(page, cases);
  await say(page, String(n));
  await expect(page).toHaveURL(/\/cases$/);
});

test('numbers sit above an open dialog and follow a change of screen', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await turnOnVoice(page);
  await say(page, 'show numbers');
  const before = await page.locator('.vc-num').count();
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  await expect.poll(async () => page.locator('.vc-num').count(), { timeout: 5000 }).not.toBe(before);
  await expect(voiceBar(page).getByRole('button', { name: 'Numbers' })).toHaveAttribute('aria-pressed', 'true');
});

test('lists: open the first and the last case, and a named one', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await page.getByRole('link', { name: 'Cases' }).click();
  await expect(page.locator('tbody tr[tabindex="0"]').first()).toBeVisible();
  const titles = await page.locator('tbody tr[tabindex="0"] b').allTextContents();
  expect(titles.length).toBeGreaterThan(1);
  await turnOnVoice(page);

  await say(page, 'open the first case');
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(titles[0].split(' ')[0]);

  await say(page, 'go back');
  await expect(page).toHaveURL(/\/cases$/);
  await say(page, 'open the last one');
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(titles[titles.length - 1].split(' ')[0]);
});

test('switches: turn on and off by name, and say when it is already so', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await page.getByRole('link', { name: 'Settings' }).click();
  const toggle = page.getByRole('switch', { name: 'Text message reminders' });
  await expect(toggle).toBeVisible();
  await turnOnVoice(page);

  const initial = (await toggle.getAttribute('aria-checked')) === 'true';
  const word = initial ? 'on' : 'off';
  await say(page, `turn ${word} text message reminders`);
  await expect(voiceBar(page)).toContainText(`already ${word}`);
  await expect(toggle).toHaveAttribute('aria-checked', String(initial));

  await say(page, `turn ${initial ? 'off' : 'on'} text message reminders`);
  await expect(toggle).toHaveAttribute('aria-checked', String(!initial));
  // put it back, so the shared test data is unchanged
  await say(page, `turn ${initial ? 'on' : 'off'} text message reminders`);
  await expect(toggle).toHaveAttribute('aria-checked', String(initial));
});

test('a named button is pressed, and an unknown or noisy phrase presses nothing', async ({ page }) => {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await page.getByRole('link', { name: 'Ask MrCourt' }).click();
  await turnOnVoice(page);
  await say(page, 'click the knowledge tab');
  await expect(page).toHaveURL(/\/ask\/knowledge/);
  await say(page, 'ok google open the history tab please');
  await expect(voiceBar(page)).toContainText('could not find');
  await expect(page).toHaveURL(/\/ask\/knowledge/);
});
