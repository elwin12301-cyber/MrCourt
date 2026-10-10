import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { createClientScenario } from './support/helpers';

async function open(page: Page) {
  await page.goto('/ask/text');
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Text Assistant' })).toHaveAttribute('aria-selected', 'true');
}

async function newConversation(page: Page) {
  await page.getByRole('button', { name: 'New conversation' }).click();
  await expect(page.getByLabel('Type a line')).toBeVisible();
}

async function speakOnce(page: Page) {
  const mic = page.getByRole('button', { name: 'Record a turn' });
  await mic.click();
  await expect(mic).toHaveAttribute('aria-pressed', 'true');
  await page.waitForTimeout(1200);
  await mic.click();
}

test('the tab tells people their voice goes to the speech service and is not stored', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    const note = s.advocate.locator('#text-assistant .advicenotice');
    await expect(note).toContainText('Sarvam AI');
    await expect(note).toContainText('does not store the audio');
  } finally {
    await s.close();
  }
});

test('speaking adds a transcribed line; typed lines can be added, edited and removed', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    await newConversation(s.advocate);
    await speakOnce(s.advocate);
    const lines = s.advocate.getByRole('list', { name: 'Lines' }).getByRole('listitem');
    await expect(lines.first()).toContainText('Spoken line from the speech service');
    await expect(lines.first()).toContainText('Voice');

    await s.advocate.getByLabel('Type a line').fill('A typed line about the hearing');
    await s.advocate.getByRole('button', { name: 'Add line' }).click();
    await expect(lines).toHaveCount(2);
    await expect(lines.nth(1)).toContainText('Typed');

    await lines.nth(1).getByRole('button', { name: /^Edit line/ }).click();
    await lines.nth(1).getByRole('textbox', { name: 'Edit line' }).fill('A corrected typed line');
    await lines.nth(1).getByRole('button', { name: 'Save' }).click();
    await expect(lines.nth(1)).toContainText('A corrected typed line');

    await lines.first().getByRole('button', { name: /^Remove line/ }).click();
    await expect(lines).toHaveCount(1);
  } finally {
    await s.close();
  }
});

test('the conversation downloads as a PDF', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    await newConversation(s.advocate);
    await s.advocate.getByLabel('Type a line').fill('Line for the PDF');
    await s.advocate.getByRole('button', { name: 'Add line' }).click();
    await expect(s.advocate.getByRole('list', { name: 'Lines' }).getByRole('listitem')).toHaveCount(1);
    const [download] = await Promise.all([s.advocate.waitForEvent('download'), s.advocate.getByRole('link', { name: 'Download PDF' }).click()]);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(chunk as Buffer);
    expect(Buffer.concat(chunks).subarray(0, 4).toString()).toBe('%PDF');
  } finally {
    await s.close();
  }
});

test('an advocate adds a conversation to the knowledge base; a client cannot', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    await newConversation(s.advocate);
    await s.advocate.getByLabel('Type a line').fill('The zorvexnote covenant needs eleven months of notice.');
    await s.advocate.getByRole('button', { name: 'Add line' }).click();
    await s.advocate.getByRole('button', { name: 'Add to the knowledge base' }).click();
    await expect(s.advocate.getByText(/Added to the knowledge base as/)).toBeVisible();
    await s.advocate.getByRole('tab', { name: 'Knowledge Base' }).click();
    await expect(s.advocate.locator('tbody tr', { hasText: 'zorvexnote' })).toContainText('Private to you');

    await open(s.client);
    await newConversation(s.client);
    await s.client.getByLabel('Type a line').fill('A client note');
    await s.client.getByRole('button', { name: 'Add line' }).click();
    await expect(s.client.getByRole('link', { name: 'Download PDF' })).toBeVisible();
    await expect(s.client.getByRole('button', { name: 'Add to the knowledge base' })).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('deleting a conversation removes it from the tab, but its History entry stays', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    await newConversation(s.advocate);
    const marker = `Meeting notes ${Date.now()}`;
    await s.advocate.getByLabel('Type a line').fill(marker);
    await s.advocate.getByRole('button', { name: 'Add line' }).click();
    await expect(s.advocate.getByRole('list', { name: 'Lines' }).getByRole('listitem')).toHaveCount(1);
    await s.advocate.getByRole('button', { name: 'Delete conversation' }).click();
    await expect(s.advocate.getByText('Deleting removes it from this tab. Its entry stays in History.')).toBeVisible();
    await s.advocate.getByRole('button', { name: 'Yes, delete' }).click();
    await expect(s.advocate.getByText('You have no conversations yet.')).toBeVisible();

    await s.advocate.getByRole('tab', { name: 'History' }).click();
    await s.advocate.getByLabel('Filter by assistant').selectOption('text');
    const row = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem').filter({ hasText: marker }).first();
    await expect(row).toContainText('Saved');
    await row.getByRole('button', { name: /^Open/ }).click();
    await expect(row).toContainText('was deleted from the Text Assistant tab');
    await expect(row.getByRole('list', { name: 'Conversation lines' })).toContainText(marker);
  } finally {
    await s.close();
  }
});

test('conversations are private to their owner', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await open(s.advocate);
    await newConversation(s.advocate);
    await s.advocate.getByLabel('Type a line').fill('Only for me');
    await s.advocate.getByRole('button', { name: 'Add line' }).click();
    await expect(s.advocate.getByRole('list', { name: 'Lines' }).getByRole('listitem')).toHaveCount(1);
    const mine = await (await s.advocate.request.get('/api/v1/text/conversations')).json();
    await open(s.client);
    await expect(s.client.getByText('You have no conversations yet.')).toBeVisible();
    expect((await s.client.request.get(`/api/v1/text/conversations/${mine[0].id}`)).status()).toBe(404);
  } finally {
    await s.close();
  }
});

test('"Better for Tamil" on the Ask tab sends the voice to the speech service and fills the question box', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.advocate.goto('/ask');
    await expect(s.advocate.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    await s.advocate.getByLabel(/Better for Tamil/).check();
    await s.advocate.getByLabel('Speak in').selectOption('ta-IN');
    const mic = s.advocate.getByRole('button', { name: 'Voice input' });
    await mic.click();
    await expect(s.advocate.getByRole('status').filter({ hasText: 'Recording' })).toBeVisible();
    await s.advocate.waitForTimeout(1200);
    await mic.click();
    await expect(s.advocate.getByLabel('Ask a legal question')).toHaveValue('வணக்கம் from the speech service');
  } finally {
    await s.close();
  }
});
