import { expect, test } from './support/test';
import { createClientScenario, newAdminPage } from './support/helpers';

const COVERED = 'What is the punishment for cheque bounce under Section 138 of the NI Act?';

test('History separates Ask and Assistant from the Text Assistant, and combines with the other filters', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const p = s.advocate;
    await p.request.post('/api/v1/questions', { data: { text: COVERED } });
    const made = await (await p.request.post('/api/v1/text/conversations', { data: { language: 'en-IN' } })).json();
    await p.request.post(`/api/v1/text/conversations/${made.id}/lines`, { data: { text: 'A spoken note for the file', source: 'voice' } });

    await p.goto('/ask/history');
    const rows = p.getByRole('list', { name: 'Your questions' }).getByRole('listitem');
    await expect(rows).toHaveCount(2);

    const filter = p.getByLabel('Filter by assistant');
    await filter.selectOption('text');
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText('A spoken note for the file');
    await expect(rows.first()).toContainText('Saved');
    await expect(rows.first().getByRole('button', { name: /^Ask again/ })).toHaveCount(0);

    await filter.selectOption('ask');
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(COVERED);

    await filter.selectOption('');
    await p.getByLabel('Filter by outcome').selectOption('answered');
    await expect(rows).toHaveCount(1); // saved conversations have no outcome
    await expect(rows.first()).toContainText(COVERED);
  } finally {
    await s.close();
  }
});

test('a citation opens to the passage, with its document and page', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const p = s.advocate;
    await p.goto('/ask');
    await p.getByLabel('Ask a legal question').fill(COVERED);
    await p.getByRole('button', { name: 'Send' }).click();
    const answer = p.locator('.card.a').last();
    await expect(answer.locator('.src').first()).toContainText('Section 138');
    await answer.getByRole('button', { name: 'Read source 1' }).click();
    const source = answer.getByRole('region', { name: 'Source 1' });
    await expect(source).toContainText('Negotiable Instruments Act');
    await expect(source).toContainText('two years');
    await answer.getByRole('button', { name: 'Hide source 1' }).click();
    await expect(source).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('an old answer whose source was removed still shows its label and says the text is gone', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const word = `quillon${Date.now().toString(36)}`;
    await admin.page.request.post('/api/v1/knowledge/documents', {
      multipart: { title: `Gone ${word}`, citation: `Gone Act ${word}`, text: `The ${word} covenant requires nine months of notice.` },
    });
    const asked = await (await s.advocate.request.post('/api/v1/questions', { data: { text: `How many months of notice does the ${word} covenant require?` } })).json();
    expect(asked.outcome).toBe('cited');
    const docs = await (await admin.page.request.get('/api/v1/knowledge/documents')).json();
    const doc = docs.find((d: { title: string }) => d.title === `Gone ${word}`);
    await admin.page.request.delete(`/api/v1/knowledge/documents/${doc.id}`);

    await s.advocate.goto('/ask/history');
    const row = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: word }).first();
    await row.getByRole('button', { name: /^Open/ }).click();
    const gone = row.locator('.src').filter({ hasText: `Gone Act ${word}` });
    await expect(gone).toHaveCount(1);
    await gone.getByRole('button', { name: /^Read source/ }).click();
    await expect(gone.getByRole('region')).toContainText('has since been removed');
  } finally {
    await admin.close();
    await s.close();
  }
});
