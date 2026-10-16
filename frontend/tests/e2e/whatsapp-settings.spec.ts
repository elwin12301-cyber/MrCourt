import type { APIRequestContext, Page } from '@playwright/test';
import { expect, test } from './support/test';
import { expectNoA11yViolations, setTheme } from './support/helpers';

let counter = 0;
const unique = () => `${Date.now()}${process.pid}${counter++}`;
const newPhone = () => `+9198${unique().slice(-8).padStart(8, '1')}`;
const PASSWORD = 'a-strong-password';

async function lastCodeFor(request: APIRequestContext, phone: string): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const messages = (await (await request.get('/api/v1/dev/messages')).json()) as { to: string; text: string }[];
    const code = messages.find((m) => m.to === phone)?.text.match(/\b(\d{6})\b/)?.[1];
    if (code) return code;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`No text message was sent to ${phone}`);
}

/** A new client with a verified phone, on the Settings screen. */
async function verifiedClientInSettings(page: Page, verify = true) {
  const phone = newPhone();
  await page.goto('/register/petitioner');
  await page.getByLabel('Username', { exact: true }).fill(`u${unique()}`);
  await page.getByLabel('Full name').fill('Nina Rao');
  await page.getByLabel(/^Email/).fill(`wa-${unique()}@example.com`);
  await page.getByLabel('Mobile number').fill(phone);
  await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Verify your mobile number' })).toBeVisible();
  if (verify) {
    await page.getByLabel('6-digit code').fill(await lastCodeFor(page.request, phone));
    await page.getByRole('button', { name: 'Verify', exact: true }).click();
    await expect(page.getByText('Your cases will appear here')).toBeVisible();
  } else {
    await page.getByRole('button', { name: 'Verify later' }).click();
  }
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('region', { name: 'WhatsApp' })).toBeVisible();
}

test('a person links WhatsApp, switches a kind on and off, and unlinks; everything starts off', async ({ page }) => {
  await verifiedClientInSettings(page);
  const card = page.locator('section.wa');
  await expect(card).toContainText('Not linked');
  await expect(card).toContainText('Every kind of message is off until you switch it on');

  await card.getByRole('button', { name: 'Link WhatsApp' }).click();
  await expect(card).toContainText('Linked');
  await expect(card.getByRole('status')).toContainText('Nothing is sent until you switch a kind on');
  for (const name of ['Sign-in and verification codes', 'Hearing reminders', 'Case updates']) {
    await expect(card.getByRole('switch', { name })).toHaveAttribute('aria-checked', 'false');
  }
  await expect(card.getByRole('switch', { name: 'Client activity' })).toHaveCount(0); // that kind is for advocates

  const reminders = card.getByRole('switch', { name: 'Hearing reminders' });
  await reminders.click();
  await expect(reminders).toHaveAttribute('aria-checked', 'true');
  await expect(card).toContainText('You agreed on');
  await page.reload();
  await expect(page.locator('section.wa').getByRole('switch', { name: 'Hearing reminders' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.locator('section.wa').getByRole('switch', { name: 'Case updates' })).toHaveAttribute('aria-checked', 'false');

  await page.locator('section.wa').getByRole('switch', { name: 'Hearing reminders' }).click();
  await expect(page.locator('section.wa').getByRole('switch', { name: 'Hearing reminders' })).toHaveAttribute('aria-checked', 'false');

  await page.locator('section.wa').getByRole('button', { name: 'Unlink WhatsApp' }).click();
  await expect(page.locator('section.wa')).toContainText('Not linked');
  await expect(page.locator('section.wa').getByRole('switch')).toHaveCount(0);
});

test('without a verified number the card asks to verify first and cannot link', async ({ page }) => {
  await verifiedClientInSettings(page, false);
  const card = page.locator('section.wa');
  await expect(card).toContainText('Verify your mobile number above first');
  await expect(card.getByRole('button', { name: 'Link WhatsApp' })).toBeDisabled();
});

test('the WhatsApp card has no accessibility violations in both themes', async ({ page }) => {
  await verifiedClientInSettings(page);
  await page.locator('section.wa').getByRole('button', { name: 'Link WhatsApp' }).click();
  await expect(page.locator('section.wa').getByRole('switch', { name: 'Hearing reminders' })).toBeVisible();
  for (const theme of ['light', 'dark'] as const) {
    await setTheme(page, theme);
    await expectNoA11yViolations(page);
  }
});
