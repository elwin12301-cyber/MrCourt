import { expect, test } from './support/test';
import { signInAs } from './support/helpers';
import { fakeVoice, say, turnOnVoice, voiceBar } from './support/voice';

/**
 * US1: every menu item, tab and section opens by name, for all three roles, in English, in mixed phrases and in
 * the other languages. Voice control is switched on once and keeps listening.
 */

const ADVOCATE = 'rohan.sharma@example.com';
const CLIENT = 'anita.sharma@example.com';
const ADMIN = 'admin@example.com';

test.describe('advocate', () => {
  test('moves around the whole app by saying names', async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, ADVOCATE);
    await turnOnVoice(page);

    const steps: [string, RegExp][] = [
      ['open cases', /\/cases$/],
      ['go to Ask MrCourt', /\/ask/],
      ['open the history tab', /\/ask\/history/],
      ['go to drafts', /\/drafts/],
      ['go to settings', /\/settings/],
      ['go to dashboard', /\/dashboard/],
    ];
    for (const [phrase, url] of steps) {
      await say(page, phrase);
      await expect(page).toHaveURL(url);
      await expect(voiceBar(page)).toContainText('Heard: “' + phrase + '”');
    }
    // "go back" returns to the previous screen
    await say(page, 'go to settings');
    await expect(page).toHaveURL(/\/settings/);
    await say(page, 'go back');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('understands mixed Tamil, Hindi and English phrases', async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, ADVOCATE);
    await turnOnVoice(page);
    for (const [phrase, url] of [
      ['cases open pannu', /\/cases$/],
      ['dashboard ku po', /\/dashboard/],
      ['settings kholo', /\/settings/],
      ['chella to dashboard', /\/dashboard/],
      ['cases par jao', /\/cases$/],
      ['डैशबोर्ड खोलो', /\/dashboard/],
    ] as [string, RegExp][]) {
      await say(page, phrase);
      await expect(page).toHaveURL(url);
    }
  });

  test('says so, and does nothing, for a screen it does not have or a phrase it does not understand', async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, ADVOCATE);
    await turnOnVoice(page);
    await say(page, 'open audit log');
    await expect(voiceBar(page)).toContainText('not available to you');
    await say(page, 'open the unicorn page');
    await expect(voiceBar(page)).toContainText('could not find');
    await say(page, 'blah blah blah');
    await expect(voiceBar(page)).toContainText('did not understand');
    await expect(page).toHaveURL(/\/dashboard/);
  });
});

test.describe('client', () => {
  test('reaches the client menu and cannot reach administrator pages', async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, CLIENT);
    await turnOnVoice(page);
    await say(page, 'open my cases');
    await expect(page).toHaveURL(/\/cases$/);
    await say(page, 'open updates');
    await expect(page).toHaveURL(/\/updates/);
    await say(page, 'go to ask mrcourt');
    await expect(page).toHaveURL(/\/ask/);
    await say(page, 'open audit log');
    await expect(voiceBar(page)).toContainText('not available to you');
    await say(page, 'open drafts');
    await expect(page).not.toHaveURL(/\/drafts/);
  });
});

test.describe('administrator', () => {
  test('opens every administrator page by name', async ({ page }) => {
    await fakeVoice(page);
    await signInAs(page, ADMIN);
    await turnOnVoice(page);
    for (const [phrase, url] of [
      ['open advocates', /\/admin\/advocates/],
      ['open clients', /\/admin\/clients/],
      ['open cases', /\/admin\/cases/],
      ['open verifications', /\/admin\/verifications/],
      ['open messages', /\/admin\/messages/],
      ['open audit log', /\/admin\/audit/],
      ['go to ask mrcourt', /\/ask/],
      ['go to settings', /\/settings/],
      ['go to overview', /\/dashboard/],
    ] as [string, RegExp][]) {
      await say(page, phrase);
      await expect(page).toHaveURL(url);
    }
  });
});
