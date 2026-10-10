import { expect, test } from './support/test';
import { BASE_URL, createClientScenario, signInAs } from './support/helpers';

const SEEDED_CLIENT = 'anita.sharma@example.com';

test.describe('seeded client (Anita)', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, SEEDED_CLIENT);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Anita');
  });

  test('the dashboard is made for a client: my cases, status, next hearing, my lawyer', async ({ page }) => {
    // Client navigation, not the advocate's.
    await expect(page.getByRole('link', { name: 'My cases' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Drafts' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Cases', exact: true })).toHaveCount(0);

    const card = page.locator('.clientcase');
    await expect(card).toHaveCount(1);
    await expect(card).toContainText('Sharma v. Verma Traders');
    await expect(card).toContainText('Hearing scheduled');
    await expect(card).toContainText('Status updated');
    await expect(card).toContainText('Next hearing:');
    await expect(card).toContainText('Saket District Court');
    await expect(card).toContainText('My lawyer: Adv. Rohan Sharma');
    await expect(page.getByText('Active cases')).toHaveCount(0); // no advocate statistics
  });

  test('the case page answers "where does my case stand and what happens next"', async ({ page }) => {
    await page.locator('.clientcase').click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
    await expect(page.getByText('Hearing scheduled').first()).toBeVisible();
    await expect(page.getByText(/Status updated/).first()).toBeVisible();

    // Next hearing with a general description, labelled and carrying the disclaimer.
    const next = page.locator('.card', { hasText: 'Next hearing' }).first();
    await expect(next.locator('.hearingdesc')).toContainText('General information');
    await expect(next.locator('.hearingdesc')).toContainText('witnesses give their statements');
    await expect(next.locator('.hearingdesc')).toContainText('Informational only, not legal advice.');

    // Timeline, newest first, shared items only.
    const timeline = page.locator('.tl li');
    await expect(timeline.first()).toContainText('Your next hearing is for evidence. Please bring a photo ID.');
    await expect(page.getByText('Respondent appeared and was given time to reply.').first()).toBeVisible();

    // Documents: the shared one only.
    await expect(page.getByText('Legal notice.pdf')).toBeVisible();
    await expect(page.getByText('Cheque copy.pdf')).toHaveCount(0);
    await expect(page.getByText('Dishonour memo.pdf')).toHaveCount(0);
  });

  test('nothing private appears anywhere on the case page', async ({ page }) => {
    await page.locator('.clientcase').click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
    const body = await page.locator('main').innerText();
    for (const secret of [
      'Private',
      'cross-examination',
      'Settlement discussed',
      'Do I need to attend',
      'Ravi Mehta',
    ]) {
      expect(body, `should not contain "${secret}"`).not.toContain(secret);
    }
    await expect(page.getByRole('tab', { name: 'Notes' })).toHaveCount(0);
  });

  test('My cases lists the case and opens it from the keyboard', async ({ page }) => {
    await page.getByRole('link', { name: 'My cases' }).click();
    await expect(page.getByRole('heading', { name: 'My cases', level: 1 })).toBeVisible();
    const card = page.locator('.clientcase').first();
    await card.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/cases\/[0-9a-f-]+$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
  });

  test('a plain-language explanation is one click away', async ({ page }) => {
    await page.locator('.clientcase').click();
    await page.getByText('What does “Hearing” mean?').click();
    await expect(page.getByText('A date on which the case is listed before the court.')).toBeVisible();
  });

  test('no horizontal scrolling on the client screens', async ({ page }) => {
    for (const path of ['/dashboard', '/cases']) {
      await page.goto(path);
      await expect(page.locator('.clientcase').first()).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, path).toBeLessThanOrEqual(0);
    }
    await page.locator('.clientcase').first().click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sharma v. Verma Traders');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test('a client with no cases is told how invitations work', async ({ page }) => {
  const registered = await page.request.post('/api/v1/auth/register', {
    data: {
      role: 'petitioner',
      full_name: 'Nina Rao',
      email: `nina-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`,
      password: 'a-strong-password',
    },
  });
  expect(registered.ok()).toBeTruthy();
  await page.goto('/dashboard');
  await expect(page.getByText('Your cases will appear here')).toBeVisible();
  await expect(page.getByText(/invites you to a case/)).toBeVisible();
});

test('a new case with nothing shared yet shows honest empty states', async ({ browser, page }) => {
  const scenario = await createClientScenario(browser, page);
  try {
    const client = scenario.client;
    await client.goto('/dashboard');
    const card = client.locator('.clientcase');
    await expect(card).toContainText(scenario.caseTitle);
    await expect(card).toContainText('Your lawyer has not shared a status yet');
    await expect(card).toContainText('No hearing scheduled yet');

    await card.click();
    await expect(client.getByText('No hearing scheduled yet').first()).toBeVisible();
    await expect(client.getByText('Nothing has been shared yet.')).toBeVisible();
    await expect(client.getByText('Your lawyer has not shared any documents yet.')).toBeVisible();
    await expect(client.getByText('Not shared yet')).toBeVisible();
  } finally {
    await scenario.close();
  }
});

test('a client cannot open a case they were not invited to', async ({ page }) => {
  await signInAs(page, SEEDED_CLIENT);
  await expect(page.locator('.clientcase')).toBeVisible();
  await page.goto('/cases/00000000-0000-0000-0000-000000000000');
  await expect(page.getByRole('heading', { name: 'Case not found' })).toBeVisible();
  expect(BASE_URL).toContain('5174');
});

test('a status that uses a legal word comes with a plain explanation', async ({ browser, page }) => {
  const scenario = await createClientScenario(browser, page);
  try {
    await scenario.advocate.request.put(`/api/v1/cases/${scenario.caseId}/client-status`, { data: { status: 'awaiting_order' } });
    await scenario.client.goto(`/cases/${scenario.caseId}`);
    await expect(scenario.client.getByText('Awaiting order').first()).toBeVisible();
    await scenario.client.getByText('What does “Order” mean?').click();
    await expect(scenario.client.getByText('A written decision or direction from the court.')).toBeVisible();

    await scenario.advocate.request.put(`/api/v1/cases/${scenario.caseId}/client-status`, { data: { status: 'notice_stage' } });
    await scenario.client.reload();
    await scenario.client.getByText('What does “Notice” mean?').click();
    await expect(scenario.client.getByText(/formally tells someone about a claim/)).toBeVisible();
  } finally {
    await scenario.close();
  }
});
