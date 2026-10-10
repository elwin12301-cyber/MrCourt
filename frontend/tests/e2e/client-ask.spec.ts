import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

const PERSONAL = 'Should I accept the settlement offer in my case?';

test.describe('client', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'anita.sharma@example.com');
    await expect(page.locator('.clientcase')).toBeVisible();
  });

  test('"Who can see my case" names the lawyer and counts other people without naming them', async ({ page }) => {
    await page.locator('.clientcase').click();
    const panel = page.locator('#who-can-see');
    await expect(panel).toContainText('Adv. Rohan Sharma');
    await expect(panel).toContainText('can see this case, and the questions you send about it, since');
    await expect(panel).toContainText('1 other person');
    await expect(panel).toContainText('cannot see your questions');
    await expect(panel).not.toContainText('Ravi');
  });

  test('a general question is answered with citations, the disclaimer and the lawyer reminder', async ({ page }) => {
    await page.getByRole('link', { name: 'Ask MrCourt' }).click();
    await page.getByRole('button', { name: 'Cheque bounce, S.138' }).click();
    const answer = page.locator('.card.a').last();
    await expect(answer.locator('.src', { hasText: 'Negotiable Instruments Act, 1881 · Section 138' })).toBeVisible();
    await expect(answer.getByText('Informational only, not legal advice.')).toBeVisible();
    await expect(answer.getByText('For advice about your own case, please ask your lawyer.')).toBeVisible();
    await expect(answer.getByRole('note')).toHaveCount(0); // not about their own case
  });

  test('a question about their own case points to their lawyer', async ({ page }) => {
    await page.getByRole('link', { name: 'Ask MrCourt' }).click();
    await page.getByLabel('Ask a legal question').fill(PERSONAL);
    await page.getByRole('button', { name: 'Send' }).click();

    const answer = page.locator('.card.a').last();
    const notice = answer.getByRole('note');
    await expect(notice).toContainText('MrCourt cannot advise on your case. Please ask your lawyer.');
    await expect(answer.getByText('Informational only, not legal advice.')).toBeVisible();
    await expect(answer.getByText('For advice about your own case, please ask your lawyer.')).toBeVisible();

    await notice.getByRole('link', { name: 'Ask your lawyer' }).click();
    await expect(page).toHaveURL(/\/cases$/);
  });

  test('asked from inside a case, the link goes straight to the question box', async ({ page }) => {
    await page.locator('.clientcase').click();
    await page.getByRole('button', { name: 'Ask MrCourt a general legal question' }).click();
    await expect(page).toHaveURL(/\/ask$/);
    await page.getByLabel('Ask a legal question').fill(PERSONAL);
    await page.getByRole('button', { name: 'Send' }).click();

    const link = page.locator('.card.a').last().getByRole('link', { name: 'Ask your lawyer' });
    await expect(link).toHaveAttribute('href', /\/cases\/[0-9a-f-]+#ask-lawyer$/);
    await link.click();
    await expect(page.getByRole('heading', { name: 'Ask your lawyer', level: 2 })).toBeVisible();
    await expect(page.getByLabel('Your question')).toBeVisible();
  });

  test('nothing about the case is used or shown in a general answer', async ({ page }) => {
    await page.locator('.clientcase').click();
    await page.getByRole('button', { name: 'Ask MrCourt a general legal question' }).click();
    await page.getByRole('button', { name: 'Cheque bounce, S.138' }).click();
    const text = await page.locator('.card.a').last().innerText();
    expect(text).not.toContain('Sharma v. Verma Traders');
    expect(text).not.toContain('Verma Traders');
  });
});

test('advocates are not shown the client notice or reminder', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await page.getByRole('link', { name: 'Ask MrCourt' }).click();
  await page.getByLabel('Ask a legal question').fill(PERSONAL);
  await page.getByRole('button', { name: 'Send' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer.getByText('Informational only, not legal advice.')).toBeVisible();
  await expect(answer.getByRole('note')).toHaveCount(0);
  await expect(answer.getByText('please ask your lawyer')).toHaveCount(0);
});
