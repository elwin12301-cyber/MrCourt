import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { expectNoA11yViolations, newAdvocateWithCase, setTheme, signInAs } from './support/helpers';

// A FICTIONAL judgment in the layout of a High Court second appeal.
const JUDGMENT = [
  'S.A.No.4410 of 2019',
  'IN THE HIGH COURT OF JUDICATURE AT MADRAS',
  'RESERVED ON : 02.01.2025',
  'DELIVERED ON : 14.02.2025',
  'CORAM',
  'THE HONOURABLE MR. JUSTICE P.ILANGO',
  'K.Vasanth ... Appellant',
  'Vs',
  'M.Revathi ... Respondent',
  'Prayer: Second Appeal under Section 100 of the Code of Civil Procedure.',
  'The quokka boundary wall dispute was decided on the survey report.',
  'In the result, the Second Appeal is allowed. No costs.',
].join('\n');

async function addPrivateNote(page: Page, title: string) {
  await page.goto('/ask/knowledge');
  await page.getByRole('button', { name: 'Add a private note' }).click();
  await page.getByLabel('Title').fill(title);
  await page.getByLabel('Citation (shown in answers)').fill(`${title} citation`);
  await page.getByLabel('Text', { exact: true }).fill(JUDGMENT);
  await page.getByRole('button', { name: 'Add source' }).click();
  await expect(page.getByRole('row').filter({ hasText: title })).toContainText('Ready', { timeout: 20_000 });
}

test('an advocate sees mapped details, corrects one, and it is kept when mapped again', async ({ page }) => {
  test.setTimeout(120_000);
  const title = `Second appeal ${Date.now()}`;
  await newAdvocateWithCase(page); // a fresh advocate: adding documents is limited per person
  await addPrivateNote(page, title);
  const row = page.getByRole('row').filter({ hasText: title });
  await expect(row).toContainText('Judgment · Madras High Court · 14 Feb 2025 · S.A. 4410/2019');

  await row.getByRole('button', { name: `Show details of ${title}` }).click();
  const details = page.getByRole('region', { name: `Details of ${title}` }).or(page.locator('section', { has: page.getByText('Judges') }));
  await expect(page.getByText('P.Ilango')).toBeVisible();
  await expect(page.getByText('(Found in the text)').first()).toBeVisible();

  await page.getByRole('button', { name: 'Correct details' }).click();
  await page.getByLabel('Court', { exact: true }).last().fill('Madras High Court (Madurai Bench)');
  await page.getByRole('button', { name: 'Save corrections' }).click();
  await expect(page.getByText('Confirmed by a person').first()).toBeVisible();

  await page.getByRole('button', { name: 'Map my documents again' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'documents mapped' })).toContainText('Your corrections were kept');
  await expect(page.getByRole('row').filter({ hasText: title })).toContainText('Madras High Court (Madurai Bench)');
  await expect(details.first()).toBeVisible();

  for (const theme of ['light', 'dark'] as const) {
    await setTheme(page, theme);
    await expectNoA11yViolations(page);
  }
});

test('filters narrow the knowledge base and questions; citations show the details', async ({ page }) => {
  test.setTimeout(120_000);
  const title = `Filtered appeal ${Date.now()}`;
  await newAdvocateWithCase(page); // a fresh advocate: adding documents is limited per person
  await addPrivateNote(page, title);

  await page.locator('#kb-filter-type').selectOption('judgment');
  await page.locator('#kb-filter-year').selectOption('2025');
  await expect(page.getByRole('row').filter({ hasText: title })).toBeVisible();
  await page.getByLabel('Case number').fill('9999/1900');
  await expect(page.getByRole('row').filter({ hasText: title })).toHaveCount(0);
  // By keyboard: Tab from the last filter reaches "Clear filters".
  await page.getByLabel('Case number').press('Tab');
  await expect(page.getByRole('button', { name: 'Clear filters' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('row').filter({ hasText: title })).toBeVisible();

  await page.goto('/ask');
  await page.getByText('Limit sources').click();
  await page.locator('#ask-filter-type').selectOption('judgment');
  await page.getByLabel('Ask a legal question').fill('How was the quokka boundary wall dispute decided?');
  await page.getByRole('button', { name: 'Send' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer.locator('.srcdetails').first()).toContainText('Judgment · Madras High Court');
});

test('a client gets no private details or filter values', async ({ page, browser }) => {
  test.setTimeout(120_000);
  const title = `Private appeal ${Date.now()}`;
  await newAdvocateWithCase(page); // a fresh advocate: adding documents is limited per person
  await addPrivateNote(page, title);

  const other = await browser.newContext({ baseURL: 'http://localhost:5174' });
  try {
    const client = await other.newPage();
    await signInAs(client, 'anita.sharma@example.com');
    await client.goto('/ask/knowledge');
    await expect(client.getByRole('row').filter({ hasText: title })).toHaveCount(0);
    const years = await client.locator('#kb-filter-year option').allTextContents();
    expect(years).not.toContain('2025');
  } finally {
    await other.close();
  }
});
