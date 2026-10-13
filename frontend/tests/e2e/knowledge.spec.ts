import { expect, test } from './support/test';
import { createClientScenario, newAdminPage } from './support/helpers';

let counter = 0;
const unique = () => `${Date.now().toString(36)}${process.pid}${counter++}`.replace(/[^a-z0-9]/gi, '');

/** Two made-up words that exist nowhere else, so a question can only match this source. */
function secret() {
  const id = unique();
  return { word1: `zorvex${id}`, word2: `quillan${id}`, id };
}

test('an administrator adds a shared source, it is cited in answers, and removing it stops that', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const { word1, word2, id } = secret();
    const a = admin.page;
    await a.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Ask MrCourt' }).click();
    await expect(a.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    await a.getByRole('tab', { name: 'Knowledge Base' }).click();

    await a.getByRole('button', { name: 'Add a source' }).click();
    await a.getByLabel('Title').fill(`Shared ${id}`);
    await a.getByLabel('Citation (shown in answers)').fill(`Zorvex Act ${id}`);
    await a.getByLabel('Text', { exact: true }).fill(`The ${word1} rule says every ${word2} must be filed within eleven days.`);
    await a.getByRole('button', { name: 'Add source' }).click();
    const row = a.locator('tbody tr', { hasText: `Shared ${id}` });
    await expect(row).toContainText('Ready');
    await expect(row).toContainText('Shared');

    const ask = async () =>
      (await (await s.advocate.request.post('/api/v1/questions', { data: { text: `How many days does the ${word1} rule allow for each ${word2}?` } })).json()) as {
        outcome: string;
        citations: { label: string }[];
      };
    const cited = await ask();
    expect(cited.outcome).toBe('cited');
    expect(cited.citations[0].label).toContain(`Zorvex Act ${id}`);

    await row.getByRole('button', { name: `Remove Shared ${id}` }).click();
    await row.getByRole('button', { name: 'Yes, remove' }).click();
    await expect(a.locator('tbody tr', { hasText: `Shared ${id}` })).toHaveCount(0);
    expect((await ask()).outcome).toBe('no_reliable_source');
  } finally {
    await admin.close();
    await s.close();
  }
});

test('an advocate’s private note is hidden from clients and not used for them; the administrator sees it with its owner', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const { word1, word2, id } = secret();
    await s.advocate.goto('/ask/knowledge');
    await s.advocate.getByRole('button', { name: 'Add a private note' }).click();
    await s.advocate.getByLabel('Title').fill(`Mine ${id}`);
    await s.advocate.getByLabel('Citation (shown in answers)').fill(`My note ${id}`);
    await s.advocate.getByLabel('Text', { exact: true }).fill(`My ${word1} note: the ${word2} deadline is nine days.`);
    await s.advocate.getByRole('button', { name: 'Add source' }).click();
    const mine = s.advocate.locator('tbody tr', { hasText: `Mine ${id}` });
    await expect(mine).toContainText('Private to you');
    await expect(mine).toContainText('Ready');

    const question = { text: `What is the ${word1} note deadline for the ${word2}?` };
    expect((await (await s.advocate.request.post('/api/v1/questions', { data: question })).json()).outcome).toBe('cited');
    expect((await (await s.client.request.post('/api/v1/questions', { data: question })).json()).outcome).toBe('no_reliable_source');

    await s.client.goto('/ask/knowledge');
    await expect(s.client.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    await expect(s.client.locator('tbody tr', { hasText: `Mine ${id}` })).toHaveCount(0);

    await admin.page.goto('/ask/knowledge');
    await expect(admin.page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    // Administrators see advocates' private documents (each view is recorded), but cannot remove them.
    const adminRow = admin.page.locator('tbody tr', { hasText: `Mine ${id}` });
    await expect(adminRow).toContainText('Private ·');
    await expect(adminRow.getByRole('button', { name: /Remove/ })).toHaveCount(0);
  } finally {
    await admin.close();
    await s.close();
  }
});

test('a file that cannot be read shows Failed with a plain reason', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const { id } = secret();
    await s.advocate.goto('/ask/knowledge');
    await s.advocate.getByRole('button', { name: 'Add a private note' }).click();
    await s.advocate.getByLabel('Title').fill(`Blank ${id}`);
    await s.advocate.getByLabel('Citation (shown in answers)').fill(`Blank ${id}`);
    await s.advocate.getByLabel('File (PDF, text or scanned image)').setInputFiles({ name: 'blank.txt', mimeType: 'text/plain', buffer: Buffer.from('   \n  ') });
    await s.advocate.getByRole('button', { name: 'Add source' }).click();
    const row = s.advocate.locator('tbody tr', { hasText: `Blank ${id}` });
    await expect(row).toContainText('Failed');
    await expect(row).toContainText('No readable text');
  } finally {
    await s.close();
  }
});

test('clients can read the shared sources but cannot add or remove any', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.client.goto('/ask/knowledge');
    await expect(s.client.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    await expect(s.client.locator('tbody tr').first()).toBeVisible();
    await expect(s.client.getByRole('button', { name: /Add a/ })).toHaveCount(0);
    await expect(s.client.getByRole('button', { name: /^Remove/ })).toHaveCount(0);
  } finally {
    await s.close();
  }
});
