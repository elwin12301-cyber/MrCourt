import { expect, test } from './support/test';
import { newAdvocateWithCase, signInAs } from './support/helpers';

const ADVOCATE = 'rohan.sharma@example.com';

test.describe('advocate', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, ADVOCATE);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Adv. Sharma');
  });

  test('dashboard shows real counts, upcoming hearings and activity', async ({ page }) => {
    await expect(page.locator('.stat').filter({ hasText: 'Active cases' }).locator('b')).toHaveText('4');
    await expect(page.locator('.stat').filter({ hasText: 'Hearings this week' }).locator('b')).toHaveText('3');
    await expect(page.getByText('3 hearings this week')).toBeVisible();
    await expect(page.locator('.hear')).toHaveCount(3);
    await expect(page.getByText('Notice served in Sharma v. Verma Traders')).toBeVisible();

    await page.locator('.hear').first().click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
  });

  test('search and filters narrow the table', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await expect(page.getByText('4 active matters across 3 courts')).toBeVisible();
    await expect(page.locator('#caseRows tr')).toHaveCount(5);

    await page.getByLabel('Search cases').fill('imran');
    await expect(page.locator('#caseRows tr')).toHaveCount(1);
    await page.getByLabel('Search cases').fill('Anita'); // matches a party name only
    await expect(page.locator('#caseRows tr')).toHaveCount(1);
    await expect(page.locator('#caseRows')).toContainText('Sharma v. Verma Traders');
    await page.getByLabel('Search cases').fill('zzz');
    await expect(page.getByText('No cases match your search.')).toBeVisible();

    await page.getByLabel('Search cases').fill('');
    await page.getByRole('button', { name: 'Closed' }).click();
    await expect(page.getByRole('button', { name: 'Closed' })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#caseRows tr')).toHaveCount(1);
    await expect(page.locator('#caseRows')).toContainText('Gupta v. Gupta Estate');
    await expect(page.locator('#caseRows')).toContainText('—');
  });

  test('a case row opens with Enter from the keyboard', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    const row = page.locator('#caseRows tr').first();
    await row.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/cases\/[0-9a-f-]+$/);
  });

  test('case detail shows the overview, tabs, parties and documents', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.locator('#caseRows tr', { hasText: 'Sharma v. Verma Traders' }).click();

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
    await expect(page.locator('#cSub')).toContainText('CNR DLCT01-004512-2026 · Saket District Court');
    await expect(page.getByRole('tab')).toHaveText(['Overview', 'Hearings', 'Documents', 'Notes', 'Client view']);
    await expect(page.getByText('Anita Sharma (your client)')).toBeVisible();
    await expect(page.getByText('Verma Traders Pvt. Ltd.')).toBeVisible();
    await expect(page.getByText('Dishonour memo.pdf')).toBeVisible();
    await expect(page.getByText('Evidence stage')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ask MrCourt' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Draft document' })).toBeVisible();

    await page.getByRole('tab', { name: 'Hearings' }).click();
    await expect(page.getByRole('tab', { name: 'Hearings' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('heading', { name: 'Add a hearing' })).toBeVisible();
    await page.getByRole('tab', { name: 'Notes' }).click();
    await expect(page.getByLabel(/Private notes/)).toHaveValue(/cross-examination/);
  });

  test('a closed case says there is no hearing scheduled', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.locator('#caseRows tr', { hasText: 'Gupta v. Gupta Estate' }).click();
    await expect(page.getByText('No hearing scheduled')).toBeVisible();
  });

  test('an advocate can add a case and see it', async ({ page }) => {
    // Sign in as a throwaway advocate so the seeded advocate's counts stay stable for other tests.
    await newAdvocateWithCase(page);
    await page.goto('/dashboard');
    const cnr = `DLCT01-${Date.now() % 1000000}-2026`;
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.getByRole('button', { name: 'New case' }).click();
    await page.getByLabel('Case title').fill('Nair v. Pillai');
    await page.getByLabel('CNR number').fill(cnr);
    await page.getByLabel('Court', { exact: true }).fill('Saket District Court');
    await page.getByLabel('Your client (petitioner)').fill('Maya Nair');
    await page.getByRole('button', { name: 'Save case' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Nair v. Pillai');
    await expect(page.getByText('Maya Nair (your client)')).toBeVisible();
  });
});

test.describe('petitioner', () => {
  test('sees only the invited case, in the client view', async ({ page }) => {
    await signInAs(page, 'anita.sharma@example.com');
    await page.getByRole('link', { name: 'My cases' }).click();
    await expect(page.locator('.clientcase')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'New case' })).toHaveCount(0);

    await page.locator('.clientcase').first().click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
    await expect(page.getByRole('tab', { name: 'Notes' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Draft document' })).toHaveCount(0);
    await expect(page.getByLabel('Invite a petitioner to view this case')).toHaveCount(0);
  });
});
