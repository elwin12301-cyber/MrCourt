import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

/** A stand-in for the browser's speech recognition that the test can drive. */
async function fakeSpeech(page: Page, mode: 'works' | 'denied' | 'missing') {
  await page.addInitScript((m) => {
    const w = window as unknown as Record<string, unknown>;
    if (m === 'missing') {
      w.SpeechRecognition = undefined;
      w.webkitSpeechRecognition = undefined;
      return;
    }
    class Fake {
      lang = '';
      interimResults = false;
      continuous = false;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        (window as unknown as { __speech: unknown }).__speech = this;
        if (m === 'denied') {
          setTimeout(() => {
            this.onerror?.({ error: 'not-allowed' });
            this.onend?.();
          }, 0);
        }
      }
      stop() {
        this.onend?.();
      }
      say(...parts: string[]) {
        this.onresult?.({ results: parts.map((transcript) => [{ transcript }]) });
      }
    }
    w.SpeechRecognition = Fake;
  }, mode);
}

const say = (page: Page, ...parts: string[]) =>
  page.evaluate((p) => (window as unknown as { __speech: { say: (...a: string[]) => void } }).__speech.say(...p), parts);

async function openAsk(page: Page) {
  await signInAs(page, 'rohan.sharma@example.com');
  await page.getByRole('link', { name: 'Ask MrCourt' }).click();
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
}

test('speaking fills the question box, and the question is kept as a voice question', async ({ page }) => {
  await fakeSpeech(page, 'works');
  await openAsk(page);
  const mic = page.getByRole('button', { name: 'Voice input' });
  await expect(mic).toHaveAttribute('aria-pressed', 'false');

  await mic.click();
  await expect(mic).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('status').filter({ hasText: 'Listening' })).toBeVisible();

  const question = `What is the punishment for cheque bounce under Section 138? (voice ${Date.now()})`;
  await say(page, 'What is the punishment for cheque bounce');
  await expect(page.getByLabel('Ask a legal question')).toHaveValue('What is the punishment for cheque bounce');
  await say(page, question);
  await expect(page.getByLabel('Ask a legal question')).toHaveValue(question);

  await mic.click(); // a second press stops
  await expect(mic).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByRole('status').filter({ hasText: 'Stopped listening' })).toBeVisible();

  // The words can be corrected before sending, and it is still a voice question.
  await page.getByLabel('Ask a legal question').fill(`${question} Please explain.`);
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a').last().locator('.src', { hasText: 'Section 138' })).toBeVisible();

  await page.getByRole('tab', { name: 'History' }).click();
  const row = page.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: question });
  await expect(row).toContainText('Voice');
});

test('a typed question is kept as typed even after voice was used for an earlier one', async ({ page }) => {
  await fakeSpeech(page, 'works');
  await openAsk(page);
  const mic = page.getByRole('button', { name: 'Voice input' });
  await mic.click();
  await say(page, 'Is bail available under BNSS');
  await mic.click();
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a').last()).toBeVisible();

  const typed = `How does bail work for non-bailable offences under BNSS? (typed ${Date.now()})`;
  await page.getByLabel('Ask a legal question').fill(typed);
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a')).toHaveCount(2);
  await page.getByRole('tab', { name: 'History' }).click();
  await expect(page.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: typed })).toContainText('Typed');
});

test('a browser without speech recognition says so and typing still works', async ({ page }) => {
  await fakeSpeech(page, 'missing');
  await openAsk(page);
  await page.getByRole('button', { name: 'Voice input' }).click();
  await expect(page.getByRole('status').filter({ hasText: "Voice input isn't available" })).toBeVisible();
  await page.getByLabel('Ask a legal question').fill('What is Section 138?');
  await expect(page.getByRole('button', { name: 'Send' })).toBeEnabled();
});

test('a blocked microphone is explained', async ({ page }) => {
  await fakeSpeech(page, 'denied');
  await openAsk(page);
  await page.getByRole('button', { name: 'Voice input' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'microphone is blocked' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Voice input' })).toHaveAttribute('aria-pressed', 'false');
});

test('voice can be used with the keyboard alone, in the chosen language', async ({ page }) => {
  await fakeSpeech(page, 'works');
  await openAsk(page);
  await page.getByLabel('Speak in').selectOption('ta-IN');
  const mic = page.getByRole('button', { name: 'Voice input' });
  await mic.focus();
  await expect(mic).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(mic).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => (window as unknown as { __speech: { lang: string } }).__speech.lang)).toBe('ta-IN');
  await page.keyboard.press('Space');
  await expect(mic).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByLabel('Speak in')).toHaveValue('ta-IN');
});

test('the dashboard quick-ask card can use voice too, and the question arrives as a voice question', async ({ page }) => {
  await fakeSpeech(page, 'works');
  await signInAs(page, 'rohan.sharma@example.com');
  await page.getByRole('link', { name: 'Dashboard' }).click();
  const mic = page.locator('#quickAsk').getByRole('button', { name: 'Voice input' });
  await mic.click();
  const question = `How does bail work for non-bailable offences under BNSS? (dash ${Date.now()})`;
  await say(page, question);
  await mic.click();
  await page.locator('#quickAsk').getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page).toHaveURL(/\/ask/);
  await expect(page.locator('.card.a').last().locator('.src', { hasText: 'Section 480' })).toBeVisible();
  await page.getByRole('tab', { name: 'History' }).click();
  await expect(page.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: question })).toContainText('Voice');
});
