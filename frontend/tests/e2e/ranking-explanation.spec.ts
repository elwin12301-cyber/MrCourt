import { expect, test } from './support/test';
import { expectNoA11yViolations, setTheme, signInAs } from './support/helpers';

const CHEQUE = 'What is the punishment for cheque bounce under Section 138 of the NI Act?';

test('an administrator can see why each source ranked where it did', async ({ page }) => {
  await signInAs(page, 'admin@example.com');
  await page.goto('/ask');
  await page.getByLabel('Ask a legal question').fill(CHEQUE);
  await page.getByRole('button', { name: 'Send' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer.locator('.src', { hasText: 'Section 138' })).toBeVisible();

  await answer.getByText('Why these sources?').click();
  await expect(answer.getByText('Kind of question: What the law says')).toBeVisible();
  await expect(answer.getByText('Named in the question: Section 138 NI')).toBeVisible();
  const first = answer.locator('.rankexp li').first();
  await expect(first).toContainText('Section 138');
  await expect(first).toContainText('Named');
  await expect(first).toContainText(/Overall \d+ · word match \d+/);

  for (const theme of ['light', 'dark'] as const) {
    await setTheme(page, theme);
    await expectNoA11yViolations(page);
  }
});

test('the explanation is also in everyone’s questions', async ({ page }) => {
  await signInAs(page, 'admin@example.com');
  await page.goto('/ask');
  await page.getByLabel('Ask a legal question').fill(CHEQUE);
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a').last().locator('.src', { hasText: 'Section 138' })).toBeVisible();
  await page.goto('/ask/history');
  await page.getByLabel('Whose questions').selectOption('everyone');
  const row = page.getByRole('list', { name: 'Everyone’s questions' }).getByRole('listitem').filter({ hasText: CHEQUE }).first();
  await row.getByText('Why these sources?').click();
  await expect(row.locator('.rankexp li').first()).toContainText('Section 138');
});

test('advocates do not see the explanation', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await page.goto('/ask');
  await page.getByLabel('Ask a legal question').fill(CHEQUE);
  await page.getByRole('button', { name: 'Send' }).click();
  const answer = page.locator('.card.a').last();
  await expect(answer.locator('.src', { hasText: 'Section 138' })).toBeVisible();
  await expect(answer.getByText('Why these sources?')).toHaveCount(0);
});

test('a section that is not in the sources is reported, not replaced', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await page.goto('/ask');
  await page.getByLabel('Ask a legal question').fill('What does Section 999 of the NI Act say about cheque dishonour?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a').last()).toContainText('Not found in the sources: Section 999 NI');
});
