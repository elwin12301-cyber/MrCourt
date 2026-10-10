import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

const ADVOCATE = 'rohan.sharma@example.com';

test.beforeEach(async ({ page }) => {
  await signInAs(page, ADVOCATE);
  await page.getByRole('link', { name: 'Ask MrCourt' }).click();
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
});

test('a suggested question gets a cited answer with numbered sources and the disclaimer', async ({
  page,
}) => {
  await page.getByRole('button', { name: 'Cheque bounce, S.138' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer.getByText('Informational only, not legal advice.')).toBeVisible();
  await expect(
    answer.locator('.src', { hasText: 'Negotiable Instruments Act, 1881 · Section 138' }),
  ).toBeVisible();
  await expect(answer.locator('.src b').first()).toHaveText('[1]');
  await expect(answer).toContainText('two years');
});

test('a question with no source says so plainly, with no citations', async ({ page }) => {
  await page.getByLabel('Ask a legal question').fill('How do I register a trademark in India?');
  await page.getByRole('button', { name: 'Send' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer).toContainText('could not find a reliable source');
  await expect(answer.locator('.src')).toHaveCount(0);
  await expect(answer.getByText('Informational only, not legal advice.')).toBeVisible();
});

test('the send button is disabled until there is a question', async ({ page }) => {
  const send = page.getByRole('button', { name: 'Send' });
  await expect(send).toBeDisabled();
  await page.getByLabel('Ask a legal question').fill('   ');
  await expect(send).toBeDisabled();
  await page.getByLabel('Ask a legal question').fill('What is Section 138?');
  await expect(send).toBeEnabled();
});

test('the dashboard quick-ask card opens Ask MrCourt with the answer', async ({ page }) => {
  await page.getByRole('link', { name: 'Dashboard' }).click();
  await page.getByLabel('Ask a legal question').fill('How does bail work for non-bailable offences under BNSS?');
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page).toHaveURL(/\/ask/);
  const answer = page.locator('.card.a').last();
  await expect(answer.locator('.src', { hasText: 'Section 480' })).toBeVisible();
  // Reloading does not ask the carried-over question again.
  await page.reload();
  await expect(page.locator('.card.a')).toHaveCount(0);
});

test('voice input explains itself when the browser cannot do it', async ({ page }) => {
  await page.evaluate(() => {
    Object.defineProperty(window, 'SpeechRecognition', { value: undefined, configurable: true });
    Object.defineProperty(window, 'webkitSpeechRecognition', { value: undefined, configurable: true });
  });
  await page.getByRole('button', { name: 'Voice input' }).click();
  await expect(page.getByRole('status').filter({ hasText: "Voice input isn't available" })).toBeVisible();
});
