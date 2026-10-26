import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { createClientScenario, newAdminPage, signInAs } from './support/helpers';
import { fakeVoice, finishSpeech, say, spoken, turnOnVoice, voiceBar } from './support/voice';

/** US4: risky actions never run on one phrase; unclear phrases never act. */

const ADVOCATE = 'rohan.sharma@example.com';

async function openSettings(page: Page) {
  await fakeVoice(page);
  await signInAs(page, ADVOCATE);
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page).toHaveURL(/\/settings/);
  await turnOnVoice(page);
}

test('log out asks first, "cancel" keeps you signed in, "confirm" signs you out', async ({ page }) => {
  await openSettings(page);
  const prompt = page.getByRole('alertdialog', { name: 'Please confirm' });

  await say(page, 'log out');
  await expect(prompt).toBeVisible();
  await expect(prompt).toContainText('Say confirm or cancel');
  await expect(prompt.getByRole('button', { name: 'Cancel' })).toBeFocused(); // a stray Enter cannot confirm
  await expect(voiceBar(page)).toContainText('Waiting for your answer');
  expect(await spoken(page)).toEqual([expect.stringContaining('Say confirm or cancel')]);
  await expect(page).toHaveURL(/\/settings/);

  await finishSpeech(page); // the prompt has been read, so the app listens again
  await say(page, 'cancel');
  await expect(prompt).toHaveCount(0);
  await expect(voiceBar(page)).toContainText('Cancelled');
  await expect(page).toHaveURL(/\/settings/);

  await say(page, 'log out');
  await expect(prompt).toBeVisible();
  await finishSpeech(page);
  await say(page, 'confirm');
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
});

test('the prompt can be answered with the buttons and Escape, and any other command cancels it', async ({ page }) => {
  await openSettings(page);
  const prompt = page.getByRole('alertdialog', { name: 'Please confirm' });

  await say(page, 'sign out');
  await finishSpeech(page);
  await prompt.getByRole('button', { name: 'Cancel' }).click();
  await expect(prompt).toHaveCount(0);
  await expect(page).toHaveURL(/\/settings/);

  await say(page, 'sign out');
  await expect(prompt).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(prompt).toHaveCount(0);
  await expect(page).toHaveURL(/\/settings/);
  await expect(voiceBar(page)).toContainText('Listening'); // speaking stopped, so listening is back

  await say(page, 'sign out');
  await expect(prompt).toBeVisible();
  await finishSpeech(page);
  await say(page, 'open cases'); // anything but "confirm" cancels
  await expect(prompt).toHaveCount(0);
  await expect(voiceBar(page)).toContainText('Cancelled');
  await expect(page).toHaveURL(/\/settings/);
});

test('"confirm" with nothing pending does nothing', async ({ page }) => {
  await openSettings(page);
  await say(page, 'confirm');
  await expect(voiceBar(page)).toContainText('nothing to confirm');
  await expect(page).toHaveURL(/\/settings/);
});

test('only the first command of a phrase runs, and an unclear or low-confidence phrase does nothing', async ({ page }) => {
  await openSettings(page);
  await say(page, 'open cases and sign out');
  await expect(page).toHaveURL(/\/cases$/);
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await expect(voiceBar(page)).toContainText('I ignored');

  await say(page, 'open settings', 0.2);
  await expect(voiceBar(page)).toContainText('did not catch that clearly');
  await expect(page).toHaveURL(/\/cases$/);

  await say(page, 'mumble mumble open');
  await expect(voiceBar(page)).toContainText(/could not find|did not understand|What should I open/);
  await expect(page).toHaveURL(/\/cases$/);
});

test('a client cannot be removed from a case by one phrase', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await fakeVoice(s.advocate);
    await s.advocate.goto(`/cases/${s.caseId}`);
    await expect(s.advocate.getByRole('heading', { level: 1 })).toContainText(s.caseTitle.split(' ')[0]);
    await turnOnVoice(s.advocate);
    const remove = s.advocate.getByRole('button', { name: /^Remove / }).first();
    await expect(remove).toBeVisible();
    const who = ((await remove.getAttribute('aria-label')) ?? '').replace('Remove ', '');
    await say(s.advocate, `click remove ${who}`);
    await expect(s.advocate.getByRole('alertdialog', { name: 'Please confirm' })).toContainText('cannot be undone');
    await expect(remove).toBeVisible();
    await finishSpeech(s.advocate);
    await say(s.advocate, 'cancel');
    await expect(remove).toBeVisible();
    await say(s.advocate, `click remove ${who}`);
    await finishSpeech(s.advocate);
    await say(s.advocate, 'confirm'); // the page's own browser confirm box is accepted for this one click
    await expect(s.advocate.getByRole('button', { name: `Remove ${who}` })).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('an administrator removing a private document is told whose it is, and it is removed only after confirming', async ({ browser, page }, testInfo) => {
  // The administrator's Knowledge Base table is wider than a phone, which shrinks the page to fit and takes fixed
  // buttons out of the area the test browser will click (a real phone shows them). Phone use of this table is not
  // part of this feature; the confirmation itself is covered on the phone by the other safety tests.
  test.skip(testInfo.project.name === 'mobile', 'the administrator table is wider than a phone');
  test.slow(); // two signed-in browsers
  const id = `${Date.now().toString(36)}${process.pid}`.replace(/[^a-z0-9]/gi, '');
  await signInAs(page, ADVOCATE);
  await page.goto('/ask/knowledge');
  await page.getByRole('button', { name: 'Add a private note' }).click();
  await page.getByLabel('Title').fill(`Voice note ${id}`);
  await page.getByLabel('Citation (shown in answers)').fill(`Voice cite ${id}`);
  await page.getByLabel('Text', { exact: true }).fill(`The voice${id} rule is eleven days.`);
  await page.getByRole('button', { name: 'Add source' }).click();
  await expect(page.locator('tbody tr', { hasText: `Voice note ${id}` })).toContainText('Ready');

  const admin = await newAdminPage(browser);
  try {
    await fakeVoice(admin.page);
    await admin.page.goto('/ask/knowledge');
    await expect(admin.page.locator('tbody tr', { hasText: `Voice note ${id}` })).toContainText('Private ·');
    await turnOnVoice(admin.page);
    const prompt = admin.page.getByRole('alertdialog', { name: 'Please confirm' });

    await say(admin.page, `click remove voice note ${id}`);
    await expect(prompt).toContainText('It belongs to');
    await expect(prompt).toContainText('This cannot be undone');
    await finishSpeech(admin.page);
    await say(admin.page, 'cancel');
    await expect(admin.page.locator('tbody tr', { hasText: `Voice note ${id}` })).toHaveCount(1);

    await say(admin.page, `click remove voice note ${id}`);
    await expect(prompt).toBeVisible();
    await finishSpeech(admin.page);
    await say(admin.page, 'confirm');
    await say(admin.page, 'click yes remove'); // the page's own second step
    await expect(admin.page.locator('tbody tr', { hasText: `Voice note ${id}` })).toHaveCount(0);
  } finally {
    await admin.close();
  }
});
