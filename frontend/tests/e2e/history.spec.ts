import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { createClientScenario, newAdminPage } from './support/helpers';

const COVERED = 'What is the punishment for cheque bounce under Section 138 of the NI Act?';
const UNCOVERED = 'How do I register a trademark in India?';

const ask = (page: Page, text: string, input_method = 'typed') =>
  page.request.post('/api/v1/questions', { data: { text, input_method } });

test('history lists my questions with how they were asked and what came of them', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await ask(s.advocate, COVERED, 'voice');
    await ask(s.advocate, UNCOVERED);
    await s.advocate.goto('/ask/history');
    await expect(s.advocate.getByRole('tab', { name: 'History' })).toHaveAttribute('aria-selected', 'true');

    const rows = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem');
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toContainText(UNCOVERED);
    await expect(rows.nth(0)).toContainText('No information found');
    await expect(rows.nth(0)).toContainText('Typed');
    await expect(rows.nth(1)).toContainText(COVERED);
    await expect(rows.nth(1)).toContainText('Answered');
    await expect(rows.nth(1)).toContainText('Voice');
  } finally {
    await s.close();
  }
});

test('search and both filters narrow the list, and an empty result says so', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await ask(s.advocate, COVERED, 'voice');
    await ask(s.advocate, UNCOVERED);
    await s.advocate.goto('/ask/history');
    const rows = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem');
    await expect(rows).toHaveCount(2);

    await s.advocate.getByLabel('Search your questions').fill('trademark');
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(UNCOVERED);
    await s.advocate.getByLabel('Search your questions').fill('');

    await s.advocate.getByLabel('Filter by outcome').selectOption('answered');
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(COVERED);

    await s.advocate.getByLabel('Filter by how it was asked').selectOption('typed');
    await expect(s.advocate.getByText('No questions match.')).toBeVisible();
  } finally {
    await s.close();
  }
});

test('opening a question shows the answer again, and Ask again runs it fresh', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await ask(s.advocate, COVERED);
    await s.advocate.goto('/ask/history');
    const row = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem').first();
    await row.getByRole('button', { name: /^Open/ }).click();
    await expect(row.locator('.src', { hasText: 'Section 138' })).toBeVisible();
    await expect(row.getByText('Informational only, not legal advice.')).toBeVisible();
    await row.getByRole('button', { name: /^Close/ }).click();
    await expect(row.locator('.src')).toHaveCount(0);

    await row.getByRole('button', { name: /^Ask again/ }).click();
    await expect(s.advocate).toHaveURL(/\/ask$/);
    await expect(s.advocate.locator('.card.a').last().locator('.src', { hasText: 'Section 138' })).toBeVisible();

    await s.advocate.getByRole('tab', { name: 'History' }).click();
    await expect(s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem')).toHaveCount(2); // the old one is untouched
  } finally {
    await s.close();
  }
});

test('nobody else sees my questions, not even the person I work with', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await ask(s.advocate, COVERED);
    await s.client.goto('/ask/history');
    await expect(s.client.getByText('You have not asked anything yet.')).toBeVisible();
    const mine = await (await s.advocate.request.get('/api/v1/history')).json();
    const theirs = await s.client.request.get(`/api/v1/history/${mine.items[0].id}`);
    expect(theirs.status()).toBe(404);
  } finally {
    await s.close();
  }
});

test('an administrator can list a person’s questions, and it is recorded without the text', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const secretQuestion = `${COVERED} (admin check ${Date.now()})`;
    await ask(s.advocate, secretQuestion);
    const me = await (await s.advocate.request.get('/api/v1/me')).json();

    const a = admin.page;
    await a.goto(`/admin/advocates/${me.id}`);
    await expect(a.getByRole('heading', { name: 'Questions asked' })).toBeVisible();
    await expect(a.getByText(secretQuestion)).toHaveCount(0); // not shown until asked for
    await a.getByRole('button', { name: 'Show questions asked' }).click();
    await expect(a.getByRole('list', { name: 'Questions asked' })).toContainText(secretQuestion);

    const log = await (await a.request.get('/api/v1/admin/audit?limit=200')).json();
    const mine = log.items.filter((e: { action: string; target_id: string }) => e.action === 'history.view' && e.target_id === me.id);
    expect(mine).toHaveLength(1);
    expect(JSON.stringify(mine[0])).not.toContain(secretQuestion);
  } finally {
    await admin.close();
    await s.close();
  }
});
