import { expect, test } from './support/test';
import { expectNoA11yViolations, newAdminPage, setTheme } from './support/helpers';

test('the administrator sees message counts and the service state, and never any words or numbers', async ({ browser, page }) => {
  // One message to count: a sign-in code asked for by a seeded person (it goes to the development outbox).
  expect((await page.request.post('/api/v1/auth/otp/request', { data: { identifier: 'rohan.sharma@example.com' } })).ok()).toBeTruthy();
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    await a.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Messages' }).click();
    await expect(a.getByRole('heading', { name: 'Messages', level: 1 })).toBeVisible();

    await expect(a.getByText('Not connected')).toBeVisible(); // no WhatsApp provider in the test setup
    const counts = a.locator('#admin-messages table').first();
    await expect(counts.getByRole('row').filter({ hasText: 'Codes' }).filter({ hasText: 'Text message' })).toBeVisible();

    // Nothing that looks like a phone number, a code or message words anywhere on the page.
    const text = await a.locator('#admin-messages').innerText();
    expect(text).not.toMatch(/\d{10}/);
    expect(text).not.toMatch(/Your MrCourt code|Announcement from MrCourt/);

    // Opening the failure list is a deliberate step.
    await a.getByRole('button', { name: 'Show recent failures' }).click();
    await expect(a.getByText('No WhatsApp failures in this period.')).toBeVisible();

    await a.getByLabel('Period').selectOption('30');
    await expect(a.getByLabel('Period')).toHaveValue('30');

    for (const theme of ['light', 'dark'] as const) {
      await setTheme(a, theme);
      await expectNoA11yViolations(a);
    }
  } finally {
    await admin.close();
  }
});

test('people who are not administrators cannot open the Messages page or its data', async ({ page }) => {
  await page.goto('/admin/messages');
  await expect(page.getByRole('heading', { name: 'Messages', level: 1 })).toHaveCount(0);
  const response = await page.request.get('/api/v1/admin/messages/summary');
  expect([401, 403]).toContain(response.status());
});
