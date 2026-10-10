import type { APIRequestContext, Page } from '@playwright/test';
import { expect, test } from './support/test';

let counter = 0;
const unique = () => `${Date.now()}${process.pid}${counter++}`;
const newPhone = () => `+9198${unique().slice(-8).padStart(8, '1')}`;
const newEmail = (tag: string) => `${tag}-${unique()}@example.com`;
const PASSWORD = 'a-strong-password';

/** The newest text sent to a number, read from the development messages API. */
async function lastCodeFor(request: APIRequestContext, phone: string): Promise<string> {
  const normalised = phone.replace(/[\s-]/g, '');
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const messages = (await (await request.get('/api/v1/dev/messages')).json()) as { to: string; text: string }[];
    const hit = messages.find((m) => m.to === normalised);
    const code = hit?.text.match(/\b(\d{6})\b/)?.[1];
    if (code) return code;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`No text message was sent to ${phone}`);
}

async function fillSignUp(page: Page, role: 'advocate' | 'petitioner', email: string, phone: string) {
  await page.goto(`/register/${role}`);
  await page.getByLabel('Username', { exact: true }).fill(`u${unique()}`);
  await page.getByLabel('Full name').fill('Nina Rao');
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel('Mobile number').fill(phone);
  await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
}

test('signing up asks for a mobile number and checks it with a texted code', async ({ page }) => {
  const phone = newPhone();
  await fillSignUp(page, 'petitioner', newEmail('nina'), `${phone.slice(0, 3)} ${phone.slice(3)}`);
  await expect(page.getByRole('heading', { name: 'Verify your mobile number' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'We texted a code to •••• ' })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('Development messages');

  await page.getByLabel('6-digit code').fill(await lastCodeFor(page.request, phone));
  await page.getByRole('button', { name: 'Verify', exact: true }).click();
  await expect(page.getByText('Your cases will appear here')).toBeVisible();

  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByText('Verified', { exact: true })).toBeVisible();
  await expect(page.getByText('Hearing reminders and password reset codes are texted to this number.')).toBeVisible();
});

test('a wrong code is refused, the code can be sent again, and verifying can wait until later', async ({ page }) => {
  const phone = newPhone();
  await fillSignUp(page, 'advocate', newEmail('later'), phone);
  await expect(page.getByRole('heading', { name: 'Verify your mobile number' })).toBeVisible();

  const real = await lastCodeFor(page.request, phone);
  const wrong = real === '000000' ? '111111' : '000000';
  await page.getByLabel('6-digit code').fill(wrong);
  await page.getByRole('button', { name: 'Verify', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('not right');
  await expect(page.getByRole('button', { name: /^Resend code in \d+s$/ })).toBeDisabled();

  await page.getByRole('button', { name: 'Verify later' }).click();
  await expect(page.getByText('Active cases')).toBeVisible();

  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByText('Not verified')).toBeVisible();
  await page.getByRole('button', { name: 'Verify', exact: true }).click();
  await page.getByLabel('6-digit code').fill(await lastCodeFor(page.request, phone));
  await page.getByRole('button', { name: 'Verify', exact: true }).last().click();
  await expect(page.getByText('Your mobile number is verified.')).toBeVisible();
  await expect(page.getByText('Verified', { exact: true })).toBeVisible();
});

test('a mobile number that is already in use is refused with a clear message', async ({ page, browser }) => {
  const phone = newPhone();
  const other = await browser.newContext({ baseURL: 'http://localhost:5174' });
  try {
    const first = await other.request.post('/api/v1/auth/register', {
      data: { role: 'petitioner', full_name: 'First', email: newEmail('first'), phone, password: PASSWORD },
    });
    expect(first.ok()).toBeTruthy();
  } finally {
    await other.close();
  }
  await fillSignUp(page, 'petitioner', newEmail('second'), phone);
  await expect(page.getByRole('alert')).toContainText('already exists');
  await expect(page.getByRole('heading', { name: 'Verify your mobile number' })).toHaveCount(0);
});

test('the mobile number is required on the sign-up form', async ({ page }) => {
  await page.goto('/register/petitioner');
  await expect(page.getByLabel('Mobile number')).toHaveAttribute('required', '');
});

async function accountWithVerifiedPhone(page: Page, tag: string) {
  const email = newEmail(tag);
  const phone = newPhone();
  const made = await page.request.post('/api/v1/auth/register', {
    data: { role: 'petitioner', full_name: 'Reset Person', email, phone, password: PASSWORD },
  });
  expect(made.ok()).toBeTruthy();
  await page.request.post('/api/v1/auth/phone/request');
  const verified = await page.request.post('/api/v1/auth/phone/verify', { data: { code: await lastCodeFor(page.request, phone) } });
  expect(verified.ok()).toBeTruthy();
  await page.request.post('/api/v1/auth/logout');
  return { email, phone };
}

test('forgot password: a code is texted, a new password is chosen, and only the new one works', async ({ page }) => {
  const { email, phone } = await accountWithVerifiedPhone(page, 'forgot');
  await page.goto('/');
  await page.getByRole('button', { name: "I'm a Petitioner" }).click();
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await expect(page.getByRole('heading', { name: 'Forgot your password?' })).toBeVisible();

  await page.getByLabel('Email or phone').fill(email);
  await page.getByRole('button', { name: 'Send code' }).click();
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('If an account matches');

  await page.getByLabel('6-digit code').fill(await lastCodeFor(page.request, phone));
  await page.getByLabel('New password (at least 10 characters)', { exact: true }).fill('my-brand-new-password');
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByRole('heading', { name: 'Password changed' })).toBeVisible();

  await page.getByRole('link', { name: 'Go to sign in' }).click();
  await page.getByLabel('Email or phone').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('Invalid');
  await page.getByLabel('Password', { exact: true }).fill('my-brand-new-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'My cases' })).toBeVisible();
});

test('forgot password gives the same answer for an unknown account, and a wrong code is refused', async ({ page }) => {
  const { email, phone } = await accountWithVerifiedPhone(page, 'wrongcode');
  await page.goto('/forgot-password');
  await page.getByLabel('Email or phone').fill(newEmail('nobody'));
  await page.getByRole('button', { name: 'Send code' }).click();
  const unknown = await page.getByRole('status').textContent();

  await page.goto('/forgot-password');
  await page.getByLabel('Email or phone').fill(email);
  await page.getByRole('button', { name: 'Send code' }).click();
  expect(await page.getByRole('status').textContent()).toBe(unknown);

  const real = await lastCodeFor(page.request, phone);
  await page.getByLabel('6-digit code').fill(real === '000000' ? '111111' : '000000');
  await page.getByLabel('New password (at least 10 characters)', { exact: true }).fill('my-brand-new-password');
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByRole('alert')).toContainText('not right');
});

test('every sign-in page offers Forgot password?', async ({ page }) => {
  for (const [button, role] of [["I'm an Advocate", 'advocate'], ["I'm a Petitioner", 'petitioner']] as const) {
    await page.goto('/');
    await page.getByRole('button', { name: button }).click();
    await expect(page.getByRole('link', { name: 'Forgot password?' })).toHaveAttribute('href', `/forgot-password?role=${role}`);
  }
  await page.goto('/login/admin');
  await expect(page.getByRole('link', { name: 'Forgot password?' })).toBeVisible();
});

test('the development messages page lists what would have been texted', async ({ page }) => {
  const phone = newPhone();
  await page.request.post('/api/v1/auth/register', {
    data: { role: 'petitioner', full_name: 'Dev Page', email: newEmail('devpage'), phone, password: PASSWORD },
  });
  await page.request.post('/api/v1/auth/phone/request');
  await page.goto('/dev/messages');
  await expect(page.getByRole('heading', { name: 'Development messages' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Messages' }).getByRole('listitem').filter({ hasText: phone }).first()).toContainText('verification code');
});
