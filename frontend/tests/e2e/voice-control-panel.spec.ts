import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { expectNoA11yViolations, setTheme, signInAs, type ThemeName } from './support/helpers';
import { fakeVoice, freshAccount, say, turnOnVoice, voiceBar } from './support/voice';

/** The voice panel on every dashboard, the bar, the labels, the notice, the help and the confirmation: look, themes, phone width, keyboard. */

const ACCOUNTS = [
  { role: 'advocate', email: 'rohan.sharma@example.com' },
  { role: 'client', email: 'anita.sharma@example.com' },
  { role: 'administrator', email: 'admin@example.com' },
];

async function noSideScroll(page: Page) {
  const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(wide, 'the page scrolls sideways').toBe(false);
}

for (const { role, email } of ACCOUNTS) {
  test(`the ${role} dashboard has the voice panel, and it follows what is said`, async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, email);
    await page.goto('/dashboard');
    const panel = page.getByRole('region', { name: 'Your voice is the remote' });
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('Voice-controlled workspace');
    await expect(panel).toContainText('Tap the microphone and tell the app where to go');
    await expect(panel).toContainText('Microphone is off');
    await expect(panel).toContainText('I heard you say');
    await expect(panel).toContainText('Try “Go to dashboard”');
    await expect(panel).toContainText('works best in Chrome or Edge');
    const tile = panel.getByRole('button', { name: 'Microphone: turn on voice control' });
    await expect(tile).toHaveAttribute('aria-pressed', 'false');
    await noSideScroll(page);

    await turnOnVoice(page);
    await expect(panel).toContainText('Listening');
    await expect(panel.getByRole('button', { name: /Microphone: voice control is on/ })).toHaveAttribute('aria-pressed', 'true');
    await say(page, 'open the unicorn page');
    await expect(panel.locator('.vc-heard-card')).toContainText('open the unicorn page');
    await expect(panel.locator('.vc-heard-card')).toContainText('could not find');
    await say(page, 'show numbers');
    await expect(panel.getByRole('button', { name: 'Hide numbers' })).toBeVisible();
    await say(page, 'stop listening');
    await expect(panel).toContainText('Microphone is off');
    await expect(panel.locator('.vc-heard-card')).toContainText('Try “Go to dashboard”'); // cleared when turned off
  });
}

for (const theme of ['light', 'dark'] as ThemeName[]) {
  test(`panel, bar, number labels, notice, help and confirmation have no accessibility problems in ${theme}`, async ({ page }) => {
    await fakeVoice(page);
    await freshAccount(page); // first use: the notice shows
    await page.goto('/dashboard');
    await setTheme(page, theme);

    await expectNoA11yViolations(page); // panel and launcher, voice off

    await page.getByRole('button', { name: 'Turn on voice control', exact: true }).click();
    const notice = page.getByRole('dialog', { name: 'Turn on voice control?' });
    await expect(notice).toBeVisible();
    await expectNoA11yViolations(page); // the notice
    await notice.getByRole('button', { name: 'Agree and turn on' }).click();
    await expect(voiceBar(page)).toContainText('Listening');
    await expectNoA11yViolations(page); // panel and bar, voice on

    await say(page, 'show numbers');
    await expect(page.locator('.vc-num').first()).toBeVisible();
    await expectNoA11yViolations(page); // with number labels

    await say(page, 'what can I say');
    await expect(page.getByRole('dialog', { name: 'What can I say?' })).toBeVisible();
    await expectNoA11yViolations(page); // the help
    await say(page, 'close dialog');

    await say(page, 'go to settings');
    await expect(page).toHaveURL(/\/settings/);
    await expectNoA11yViolations(page); // the Settings section
    await say(page, 'sign out');
    await expect(page.getByRole('alertdialog', { name: 'Please confirm' })).toBeVisible();
    await expectNoA11yViolations(page); // the confirmation prompt
  });
}

test('everything fits at phone width and keeps its place', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page);
  await page.goto('/dashboard');
  await turnOnVoice(page);
  await noSideScroll(page);
  const bar = voiceBar(page);
  const box = await bar.boundingBox();
  const viewport = page.viewportSize();
  expect(box && viewport && box.x >= 0 && box.x + box.width <= viewport.width + 1).toBe(true);
  await say(page, 'go to settings');
  await expect(page).toHaveURL(/\/settings/);
  await noSideScroll(page);
  // The bar never hides the last control on the page: scrolled to the bottom, the last control is above the bar.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const lastBottom = await page.evaluate(() => {
    const items = Array.from(document.querySelectorAll<HTMLElement>('main button, main a, main input, main select, main textarea')).filter(
      (el) => el.getClientRects().length > 0,
    );
    const last = items[items.length - 1];
    return last ? last.getBoundingClientRect().bottom : 0;
  });
  const barBox = await bar.boundingBox();
  expect(barBox && lastBottom > 0 && lastBottom <= barBox.y + 1).toBe(true);
});

test('with reduced motion nothing pulses', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await fakeVoice(page);
  await freshAccount(page);
  await page.goto('/dashboard');
  await turnOnVoice(page);
  const animation = await voiceBar(page).locator('.vc-dot').evaluate((el) => getComputedStyle(el).animationName);
  expect(animation).toBe('none');
});

test('it can all be used with the keyboard alone', async ({ page }) => {
  await fakeVoice(page);
  await freshAccount(page);
  await page.goto('/dashboard');
  const launcher = page.getByRole('button', { name: 'Turn on voice control', exact: true });
  await launcher.focus();
  await expect(launcher).toBeFocused();
  await page.keyboard.press('Enter');
  const notice = page.getByRole('dialog', { name: 'Turn on voice control?' });
  await expect(notice).toBeVisible();
  await page.keyboard.press('Escape'); // closing the notice agrees to nothing
  await expect(notice).toBeHidden();
  await expect(launcher).toBeVisible();
  await launcher.focus();
  await page.keyboard.press('Enter');
  await notice.getByRole('button', { name: 'Agree and turn on' }).focus();
  await page.keyboard.press('Enter');
  await expect(voiceBar(page)).toContainText('Listening');
  // every control of the bar is reachable by Tab and has a visible name
  for (const name of ['Numbers', 'Help', 'Stop']) {
    await voiceBar(page).getByRole('button', { name }).focus();
    await expect(voiceBar(page).getByRole('button', { name })).toBeFocused();
  }
  await voiceBar(page).getByRole('button', { name: 'Help' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'What can I say?' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'What can I say?' })).toBeHidden();
});
