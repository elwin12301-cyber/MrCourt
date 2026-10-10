import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

test.beforeEach(async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await page.getByRole('link', { name: 'Ask MrCourt' }).click();
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
});

test('The Knowledge Assistant has its four tabs and opens on AI Assistant', async ({ page }) => {
  const tabs = page.getByRole('tablist', { name: 'Knowledge Assistant sections' });
  await expect(tabs.getByRole('tab')).toHaveText(['AI Assistant', 'Knowledge Base', 'Text Assistant', 'History']);
  await expect(tabs.getByRole('tab', { name: 'AI Assistant', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByLabel('Ask a legal question')).toBeVisible();
});

test('the tabs can be reached and switched by keyboard', async ({ page }) => {
  const ask = page.getByRole('tab', { name: 'AI Assistant', exact: true });
  await ask.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page).toHaveURL(/\/ask\/knowledge$/);
  await expect(page.getByRole('tab', { name: 'Knowledge Base' })).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect(page).toHaveURL(/\/ask\/text$/);
  await expect(page.getByRole('tab', { name: 'Text Assistant' })).toBeFocused();
  await page.keyboard.press('ArrowRight');
  await expect(page).toHaveURL(/\/ask\/history$/);
  await expect(page.getByRole('tab', { name: 'History' })).toHaveAttribute('aria-selected', 'true');
});

test('a covered question is cited and an uncovered one says so', async ({ page }) => {
  await page.getByLabel('Ask a legal question').fill('What is the punishment for cheque bounce under Section 138 of the NI Act?');
  await page.getByRole('button', { name: 'Send' }).click();
  const cited = page.locator('.card.a').last();
  await expect(cited.locator('.src', { hasText: 'Section 138' })).toBeVisible();

  await page.getByLabel('Ask a legal question').fill('How do I register a trademark in India?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('.card.a').last()).toContainText('could not find a reliable source');
});

test('without an AI service the screen says it is running on cited passages only', async ({ page }) => {
  await expect(page.locator('#mode-note')).toContainText('cited passages only');
});

test('the tab you are on survives a reload', async ({ page }) => {
  await page.getByRole('tab', { name: 'History' }).click();
  await page.reload();
  await expect(page.getByRole('tab', { name: 'History' })).toHaveAttribute('aria-selected', 'true');
});
