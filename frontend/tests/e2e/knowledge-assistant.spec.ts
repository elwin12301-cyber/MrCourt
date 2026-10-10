import { expect, test } from './support/test';
import { createClientScenario, newAdminPage } from './support/helpers';

const COVERED = 'What is the punishment for cheque bounce under Section 138 of the NI Act?';

async function expectTheSamePage(page: import('@playwright/test').Page) {
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
  await expect(page.getByText('Secure retrieval active')).toBeVisible();
  await expect(page.getByRole('tablist', { name: 'Knowledge Assistant sections' }).getByRole('tab')).toHaveText([
    'AI Assistant',
    'Knowledge Base',
    'Text Assistant',
    'History',
  ]);
}

test('advocates, clients and administrators get the same page, title, badge and tabs', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    for (const p of [s.advocate, s.client, admin.page]) {
      await p.goto('/ask');
      await expectTheSamePage(p);
    }
  } finally {
    await admin.close();
    await s.close();
  }
});

test('an administrator asks a cited question from the shared knowledge', async ({ browser }) => {
  const admin = await newAdminPage(browser);
  try {
    const p = admin.page;
    await p.goto('/ask');
    await p.getByLabel('Ask a legal question').fill(COVERED);
    await p.getByRole('button', { name: 'Send' }).click();
    await expect(p.locator('.card.a').last().locator('.src').first()).toContainText('Section 138');
    await p.getByRole('tab', { name: 'History' }).click();
    await expect(p.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: COVERED }).first()).toContainText('Answered');
  } finally {
    await admin.close();
  }
});

test('the History card has the search box, the dropdowns and rows with a chip, Open and Ask again', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.advocate.request.post('/api/v1/questions', { data: { text: COVERED, input_method: 'voice' } });
    await s.advocate.request.post('/api/v1/questions', { data: { text: 'How do I register a trademark in India?' } });
    await s.advocate.goto('/ask/history');
    await expect(s.advocate.getByLabel('Search your questions')).toBeVisible();
    await expect(s.advocate.getByLabel('Filter by assistant')).toHaveValue('');
    await expect(s.advocate.getByLabel('Filter by outcome')).toHaveValue('');
    await expect(s.advocate.getByText('Every question you ask is kept here, even after a conversation is deleted.')).toBeVisible();

    const rows = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem');
    const answered = rows.filter({ hasText: COVERED });
    await expect(answered).toContainText('AI Assistant');
    await expect(answered).toContainText('Voice');
    await expect(answered).toContainText('Answered');
    await expect(answered.getByRole('button', { name: /^Open/ })).toBeVisible();
    await expect(answered.getByRole('button', { name: /^Ask again/ })).toBeVisible();
    await expect(rows.filter({ hasText: 'trademark' })).toContainText('No information found');

    await s.advocate.getByLabel('Filter by outcome').selectOption('none');
    await expect(rows).toHaveCount(1);
    await s.advocate.getByLabel('Filter by outcome').selectOption('');
    await s.advocate.getByLabel('Search your questions').fill('trademark');
    await expect(rows).toHaveCount(1);
    await s.advocate.getByLabel('Search your questions').fill('nothing like this');
    await expect(s.advocate.getByText('No questions match.')).toBeVisible();
  } finally {
    await s.close();
  }
});

test('only administrators can switch to everyone’s questions, and doing so is recorded without the text', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const marker = `${COVERED} (workspace ${Date.now()})`;
    await s.advocate.request.post('/api/v1/questions', { data: { text: marker } });
    await s.advocate.goto('/ask/history');
    await expect(s.advocate.getByLabel('Whose questions')).toHaveCount(0);
    await s.client.goto('/ask/history');
    await expect(s.client.getByLabel('Whose questions')).toHaveCount(0);
    expect((await s.advocate.request.get('/api/v1/admin/questions')).status()).toBe(403);

    const a = admin.page;
    await a.goto('/ask/history');
    await a.getByLabel('Whose questions').selectOption('everyone');
    await a.getByLabel('Search your questions').fill('workspace');
    const rows = a.getByRole('list', { name: 'Everyone’s questions' }).getByRole('listitem');
    await expect(rows.filter({ hasText: marker })).toContainText('Adv. Temp Tester');
    await expect(rows.filter({ hasText: marker }).getByRole('button')).toHaveCount(0); // no Open or Ask again for others

    const log = await (await a.request.get('/api/v1/admin/audit?limit=200')).json();
    const views = log.items.filter((e: { action: string; target_type: string }) => e.action === 'history.view' && e.target_type === 'workspace');
    expect(views.length).toBeGreaterThan(0);
    expect(JSON.stringify(views)).not.toContain(marker);
  } finally {
    await admin.close();
    await s.close();
  }
});

test('clients cannot add to the knowledge base but can read it; administrators can add shared sources', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    await s.client.goto('/ask/knowledge');
    await expect(s.client.locator('tbody tr').first()).toBeVisible();
    await expect(s.client.getByRole('button', { name: /Add a/ })).toHaveCount(0);
    await admin.page.goto('/ask/knowledge');
    await expect(admin.page.getByRole('button', { name: 'Add a source' })).toBeVisible();
  } finally {
    await admin.close();
    await s.close();
  }
});
