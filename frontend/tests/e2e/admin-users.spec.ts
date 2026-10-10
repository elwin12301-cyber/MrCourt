import { expect, test } from './support/test';
import { newPerson, signInAs } from './support/helpers';

test.beforeEach(async ({ page }) => {
  await signInAs(page, 'admin@example.com');
  await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
});

test('the lists show every advocate and every client, and can be searched and filtered', async ({ browser, page }) => {
  const advocate = await newPerson(browser, 'advocate', { bar: 'D/700/2021' });
  const client = await newPerson(browser, 'petitioner');
  try {
    await page.getByRole('link', { name: 'Advocates', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Advocates', level: 1 })).toBeVisible();
    await expect(page.locator('tbody tr', { hasText: 'Adv. Rohan Sharma' })).toBeVisible();

    await page.getByLabel('Search advocates').fill(advocate.name);
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.locator('tbody tr')).toContainText('D/700/2021');
    await expect(page.locator('tbody tr')).toContainText('Active');

    await page.getByLabel('Search advocates').fill('');
    await page.getByRole('button', { name: 'Waiting for verification' }).click();
    await expect(page.locator('tbody tr', { hasText: advocate.name })).toBeVisible();
    await expect(page.locator('tbody tr', { hasText: 'Adv. Rohan Sharma' })).toHaveCount(0);

    await page.getByRole('link', { name: 'Clients', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Clients', level: 1 })).toBeVisible();
    await page.getByLabel('Search clients').fill(client.email);
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Waiting for verification' })).toHaveCount(0); // advocates only
  } finally {
    await advocate.close();
    await client.close();
  }
});

test('a person’s page shows who they are and what they are linked to', async ({ page }) => {
  await page.getByRole('link', { name: 'Clients', exact: true }).click();
  await page.getByLabel('Search clients').fill('anita');
  await page.locator('tbody tr', { hasText: 'Anita Sharma' }).click();
  await expect(page.getByRole('heading', { name: 'Anita Sharma', level: 1 })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('recorded in the audit log');
  await expect(page.locator('.card', { hasText: 'Their cases and lawyers' })).toContainText('Lawyer: Adv. Rohan Sharma');
  await page.locator('.card', { hasText: 'Their cases and lawyers' }).getByRole('link', { name: 'Sharma v. Verma Traders' }).click();
  await expect(page).toHaveURL(/\/admin\/cases\//);
});

test('corrections are saved and still there after a reload', async ({ browser, page }) => {
  const person = await newPerson(browser, 'petitioner');
  try {
    await page.goto('/admin/clients');
    await page.getByLabel('Search clients').fill(person.email);
    await page.locator('tbody tr', { hasText: person.email }).click();
    await page.getByLabel('Full name').fill('Corrected Name');
    const digits = `99${String(Date.now()).slice(-8)}`; // unique per run, so parallel runs never clash
    await page.getByLabel('Phone').fill(`+91 ${digits}`);
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText('Saved.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Corrected Name', level: 1 })).toBeVisible();

    await page.reload();
    await expect(page.getByRole('heading', { name: 'Corrected Name', level: 1 })).toBeVisible();
    await expect(page.getByLabel('Phone')).toHaveValue(`+91${digits}`);
  } finally {
    await person.close();
  }
});

test('an email that someone else uses is refused with a clear message', async ({ browser, page }) => {
  const person = await newPerson(browser, 'petitioner');
  try {
    await page.goto('/admin/clients');
    await page.getByLabel('Search clients').fill(person.email);
    await page.locator('tbody tr', { hasText: person.email }).click();
    await page.getByLabel('Email').fill('anita.sharma@example.com');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByRole('alert')).toContainText('already used by another account');
  } finally {
    await person.close();
  }
});

test('suspending signs the person out at once, and reactivating lets them back in', async ({ browser, page }) => {
  const person = await newPerson(browser, 'petitioner');
  try {
    // The client is signed in, in their own browser.
    await signInAs(person.page, person.email, person.password, 'petitioner');
    await expect(person.page.getByRole('link', { name: 'My cases' })).toBeVisible();

    await page.goto('/admin/clients');
    await page.getByLabel('Search clients').fill(person.email);
    await page.locator('tbody tr', { hasText: person.email }).click();
    await page.getByLabel('Reason for suspending').fill('Reported misuse of the messages');
    await page.getByRole('button', { name: 'Suspend account' }).click();
    await expect(page.getByText('Account suspended. They have been signed out.')).toBeVisible();
    await expect(page.getByText(/Reason: Reported misuse of the messages/)).toBeVisible();

    // The client's next action fails: they are back at the welcome screen.
    await person.page.goto('/dashboard');
    await expect(person.page.getByRole('button', { name: "I'm a Petitioner" })).toBeVisible();

    // They cannot sign in again, and are told why.
    await signInAs(person.page, person.email, person.password, 'petitioner');
    await expect(person.page.getByRole('alert')).toContainText('This account has been suspended');

    // Reactivated: they can sign in again.
    await page.getByRole('button', { name: 'Reactivate account' }).click();
    await expect(page.getByText('Account reactivated.')).toBeVisible();
    await signInAs(person.page, person.email, person.password, 'petitioner');
    await expect(person.page.getByRole('link', { name: 'My cases' })).toBeVisible();

    // The list reflects it.
    await page.goto('/admin/clients');
    await page.getByRole('button', { name: 'Suspended' }).click();
    await expect(page.locator('tbody tr', { hasText: person.email })).toHaveCount(0);
  } finally {
    await person.close();
  }
});

test('forcing a sign-out ends the session but not the account', async ({ browser, page }) => {
  const person = await newPerson(browser, 'advocate');
  try {
    await signInAs(person.page, person.email, person.password, 'advocate');
    await expect(person.page.getByRole('link', { name: 'Drafts' })).toBeVisible();

    await page.goto('/admin/advocates');
    await page.getByLabel('Search advocates').fill(person.email);
    await page.locator('tbody tr', { hasText: person.email }).click();
    await page.getByRole('button', { name: 'Sign out everywhere' }).click();
    await expect(page.getByText('Signed out everywhere.')).toBeVisible();

    await person.page.goto('/dashboard');
    await expect(person.page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
    await signInAs(person.page, person.email, person.password, 'advocate'); // still allowed
    await expect(person.page.getByRole('link', { name: 'Drafts' })).toBeVisible();
  } finally {
    await person.close();
  }
});

test('a pending Bar Council number is confirmed from the person’s page', async ({ browser, page }) => {
  const person = await newPerson(browser, 'advocate', { bar: 'D/901/2023' });
  try {
    await page.goto('/admin/advocates');
    await page.getByLabel('Search advocates').fill(person.email);
    await page.locator('tbody tr', { hasText: person.email }).click();
    await expect(page.getByText('Waiting for verification')).toBeVisible();
    await page.getByRole('button', { name: 'Confirm number' }).click();
    await expect(page.getByText('Number confirmed.')).toBeVisible();
    await expect(page.getByText('Bar Council verified')).toBeVisible();

    await signInAs(person.page, person.email, person.password, 'advocate');
    await person.page.getByRole('link', { name: 'Settings' }).click();
    await expect(person.page.getByText('Bar Council verified')).toBeVisible();
  } finally {
    await person.close();
  }
});

test('a person who deactivated their own account cannot be edited', async ({ browser, page }) => {
  const person = await newPerson(browser, 'petitioner');
  try {
    await person.page.request.post('/api/v1/auth/login', { data: { identifier: person.email, password: person.password } });
    await person.page.request.post('/api/v1/me/deactivate', { data: { acknowledge_case_retention: true } });

    await page.goto('/admin/clients');
    await page.getByRole('button', { name: 'Deactivated' }).click();
    await page.locator('tbody tr', { hasText: 'Deactivated user' }).first().click();
    await expect(page.getByText(/deactivated their account/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Suspend account' })).toHaveCount(0);
  } finally {
    await person.close();
  }
});
