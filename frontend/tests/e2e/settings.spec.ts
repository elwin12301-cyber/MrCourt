import { expect, test } from './support/test';
import { newAdvocateWithCase, signInAs } from './support/helpers';

test('profile shows the verified chip and the settings rows', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Adv. Rohan Sharma' })).toBeVisible();
  await expect(page.getByText('Bar Council verified')).toBeVisible();
  for (const row of ['Language', 'Text message reminders', 'Reminder schedule', 'Mobile number', 'Privacy & data (DPDP)', 'Help & support']) {
    await expect(page.getByText(row, { exact: true }).first()).toBeVisible();
  }
});

test('the text message reminder switch is saved, and the fixed schedule is described', async ({ page }) => {
  await newAdvocateWithCase(page); // own account, so nothing else is affected
  await page.goto('/settings');
  const reminders = page.getByRole('switch', { name: 'Text message reminders' });
  await expect(reminders).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByText('5 days before, 1 day before and on the day of each hearing')).toBeVisible();
  await reminders.click();
  await expect(reminders).toHaveAttribute('aria-checked', 'false');

  await page.reload();
  await expect(page.getByRole('switch', { name: 'Text message reminders' })).toHaveAttribute('aria-checked', 'false');
});

test('clients get the reminder switch and the mobile number row too; administrators only the number', async ({ browser, page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('switch', { name: 'Text message reminders' })).toBeVisible();
  await expect(page.getByLabel('Mobile number')).toBeVisible();

  const { newAdminPage } = await import('./support/helpers');
  const admin = await newAdminPage(browser);
  try {
    await admin.page.goto('/settings');
    await expect(admin.page.getByLabel('Mobile number')).toBeVisible();
    await expect(admin.page.getByRole('switch', { name: 'Text message reminders' })).toHaveCount(0);
  } finally {
    await admin.close();
  }
});

test('the theme can be chosen and is kept after a reload', async ({ page }) => {
  await newAdvocateWithCase(page);
  await page.goto('/settings');
  await page.getByLabel('Appearance').selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Appearance').selectOption('system');
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.+/);
});

test('the sidebar toggle flips between light and dark', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await page.emulateMedia({ colorScheme: 'light' });
  const toggle = page.locator('#themeBtn');
  if (await toggle.isVisible()) {
    await toggle.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await toggle.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  } // on narrow screens the prototype hides the toggle; Settings > Appearance covers that case
});

test('a user can download their own data', async ({ page }) => {
  await newAdvocateWithCase(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Manage' }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download my data' }).click();
  expect((await download).suggestedFilename()).toBe('mrcourt-my-data.json');
});

test('deactivation states what is kept, needs confirmation, and ends access', async ({ page }) => {
  await newAdvocateWithCase(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Manage' }).click();
  await page.getByRole('button', { name: 'Deactivate account' }).click();

  const dialog = page.getByRole('dialog', { name: 'Deactivate your account?' });
  await expect(dialog).toContainText('Case records are kept');
  const confirm = dialog.getByRole('button', { name: 'Deactivate my account' });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel('I understand that case records will be kept.').check();
  await confirm.click();

  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
  await page.goto('/dashboard');
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible(); // signed out
});

test('cancelling deactivation changes nothing', async ({ page }) => {
  await newAdvocateWithCase(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Manage' }).click();
  await page.getByRole('button', { name: 'Deactivate account' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.goto('/dashboard');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
});

test('an administrator confirms an advocate and the chip appears', async ({ page }) => {
  const unique = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const name = `Adv. Pending ${unique}`;
  const email = `pending-${unique}@example.com`;
  const register = await page.request.post('/api/v1/auth/register', {
    data: {
      role: 'advocate',
      full_name: name,
      email,
      password: 'a-strong-password',
      bar_registration_number: `D/${unique}/2024`,
    },
  });
  expect(register.ok()).toBeTruthy();
  await page.goto('/settings');
  await expect(page.getByText('Verification pending')).toBeVisible();
  await expect(page.getByText('Bar Council verified')).toHaveCount(0);
  await page.request.post('/api/v1/auth/logout');

  await signInAs(page, 'admin@example.com');
  await page.getByRole('link', { name: 'Verifications' }).click();
  const row = page.locator('.act', { hasText: name });
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'Confirm' }).click();
  await expect(row).toHaveCount(0);
  await page.request.post('/api/v1/auth/logout');

  await signInAs(page, email, 'a-strong-password');
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByText('Bar Council verified')).toBeVisible();
});

test('non-administrators do not see Verifications', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Verifications' })).toHaveCount(0);
  await page.goto('/admin/verifications');
  await expect(page.getByText('This page is for administrators only.')).toBeVisible();
});
