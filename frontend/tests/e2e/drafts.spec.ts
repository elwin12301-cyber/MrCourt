import { expect, test } from './support/test';
import { newAdvocateWithCase, signInAs } from './support/helpers';

const ADVOCATE = 'rohan.sharma@example.com';

test.describe('advocate', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, ADVOCATE);
    await page.getByRole('link', { name: 'Drafts' }).click();
    await expect(page.getByRole('heading', { name: 'Drafts', level: 1 })).toBeVisible();
  });

  test('each template shows its draft with the review flag and a version chip', async ({ page }) => {
    const names = ['Legal Notice', 'Bail Application', 'Reply to Notice', 'Affidavit'];
    for (const name of names) {
      const card = page.getByRole('button', { name, exact: true });
      await card.click();
      await expect(card).toHaveAttribute('aria-pressed', 'true');
      await expect(page.locator('#dTitle')).toContainText(name === 'Legal Notice' ? 'Legal Notice' : name);
      await expect(page.getByText('AI-generated draft · review before use')).toBeVisible();
      await expect(page.locator('.chip', { hasText: /Draft v\d+/ })).toBeVisible();
    }
  });

  test('choosing a case fills the draft from its data and keeps unknown facts as placeholders', async ({ page }) => {
    await page.getByLabel('For case').selectOption({ label: 'Sharma v. Verma Traders' });
    await expect(page.locator('#dTitle')).toHaveText('Legal Notice — Verma Traders Pvt. Ltd.');
    const letter = page.getByRole('textbox', { name: 'Draft text' });
    await expect(letter).toContainText('Anita Sharma');
    await expect(letter).toContainText('Section 138');
    await expect(letter).toContainText('[amount]');
  });

  test('editing saves a new version that survives a reload', async ({ page }) => {
    // A throwaway advocate, so the desktop and mobile runs never edit the same draft.
    const { caseTitle } = await newAdvocateWithCase(page);
    await page.goto('/drafts');
    await page.getByLabel('For case').selectOption({ label: caseTitle });
    await page.getByRole('button', { name: 'Bail Application', exact: true }).click();
    await expect(page.locator('#dTitle')).toContainText('Bail Application');
    await expect(page.locator('.chip', { hasText: 'Draft v1' })).toBeVisible();

    await page.getByRole('button', { name: 'Edit', exact: true }).click();
    const letter = page.getByRole('textbox', { name: 'Draft text' });
    await expect(letter).toHaveAttribute('contenteditable', 'true');
    await letter.press('Control+End');
    const marker = `Edited by test ${Date.now()}`;
    await page.keyboard.type(` ${marker}`);
    await page.getByRole('button', { name: 'Done', exact: true }).click();

    await expect(letter).toContainText(marker);
    await expect(page.locator('.chip', { hasText: 'Draft v2' })).toBeVisible();
    await expect(page.getByText('AI-generated draft · review before use')).toBeVisible();

    await page.reload();
    await page.getByLabel('For case').selectOption({ label: caseTitle });
    await page.getByRole('button', { name: 'Bail Application', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Draft text' })).toContainText(marker);
    await expect(page.locator('.chip', { hasText: 'Draft v2' })).toBeVisible();
  });

  test('export offers Word and PDF and downloads the chosen file', async ({ page }) => {
    await page.getByRole('button', { name: 'Export', exact: true }).click();
    await expect(page.getByRole('group', { name: 'Export format' })).toBeVisible();

    const word = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Word (.docx)' }).click();
    expect((await word).suggestedFilename()).toMatch(/\.docx$/);

    await page.getByRole('button', { name: 'Export', exact: true }).click();
    const pdf = page.waitForEvent('download');
    await page.getByRole('button', { name: 'PDF', exact: true }).click();
    expect((await pdf).suggestedFilename()).toMatch(/\.pdf$/);
  });

  test('"Draft document" on a case opens Drafts for that case', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.locator('#caseRows tr', { hasText: 'Rao v. Rao' }).click();
    await page.getByRole('button', { name: 'Draft document' }).click();
    await expect(page.getByLabel('For case')).toHaveValue(/[0-9a-f-]{36}/);
    await expect(page.locator('#dTitle')).toContainText('Legal Notice');
  });
});

test('petitioners do not get Drafts', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible(); // signed in
  await expect(page.getByRole('link', { name: 'Drafts' })).toHaveCount(0);
  await page.goto('/drafts');
  await expect(page.getByText('Drafts are available to advocates only.')).toBeVisible();
});
