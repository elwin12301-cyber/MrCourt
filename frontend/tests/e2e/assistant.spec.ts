import type { Page } from '@playwright/test';
import { expect, test } from './support/test';
import { createClientScenario } from './support/helpers';

async function openAssistant(page: Page) {
  await page.goto('/ask');
  await expect(page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
  await page.getByRole('button', { name: 'Assistant', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Assistant', exact: true })).toHaveAttribute('aria-pressed', 'true');
}

async function say(page: Page, text: string) {
  await page.getByLabel('Ask the assistant').fill(text);
  await page.getByRole('button', { name: 'Send' }).click();
}

const draftCount = async (page: Page) => ((await (await page.request.get('/api/v1/drafts')).json()) as unknown[]).length;

test('the assistant shows its steps and the privacy line, and answers from the advocate’s own cases', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await openAssistant(s.advocate);
    await expect(s.advocate.locator('#assistant-privacy')).toContainText('sent to the AI service');
    await say(s.advocate, 'What are my hearings this month?');
    const reply = s.advocate.locator('.card.a').last();
    await expect(reply.getByRole('list', { name: 'Steps taken' }).getByRole('listitem')).toHaveText(['Checked your hearings · 0 hearings']);
    await expect(reply).toContainText('You have 0 upcoming hearings.');
    await expect(reply.getByText('Informational only, not legal advice.')).toBeVisible();
  } finally {
    await s.close();
  }
});

test('a draft is only proposed; nothing exists until Confirm, and then it is an editable draft', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const before = await draftCount(s.advocate);
    await openAssistant(s.advocate);
    await say(s.advocate, 'Prepare a legal notice draft for my case');
    const reply = s.advocate.locator('.card.a').last();
    const steps = reply.getByRole('list', { name: 'Steps taken' }).getByRole('listitem');
    await expect(steps.first()).toContainText('Looked up your cases');
    await expect(steps.nth(1)).toContainText('Prepared a draft for you to confirm');
    const proposal = reply.getByRole('group', { name: 'Proposed action' });
    await expect(proposal).toContainText(`Legal Notice draft for ${s.caseTitle}`);
    expect(await draftCount(s.advocate)).toBe(before);

    await proposal.getByRole('button', { name: 'Confirm' }).click();
    await expect(proposal).toContainText('Done. The draft is in');
    expect(await draftCount(s.advocate)).toBe(before + 1);
    await expect(proposal.getByRole('button', { name: 'Confirm' })).toHaveCount(0);

    await proposal.getByRole('link', { name: 'Drafts' }).click();
    await expect(s.advocate.getByRole('heading', { name: 'Drafts', level: 1 })).toBeVisible();
  } finally {
    await s.close();
  }
});

test('declining a proposal leaves Drafts unchanged', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const before = await draftCount(s.advocate);
    await openAssistant(s.advocate);
    await say(s.advocate, 'Prepare a legal notice draft for my case');
    const proposal = s.advocate.locator('.card.a').last().getByRole('group', { name: 'Proposed action' });
    await proposal.getByRole('button', { name: 'Decline' }).click();
    await expect(proposal).toContainText('Declined. Nothing was created.');
    expect(await draftCount(s.advocate)).toBe(before);
  } finally {
    await s.close();
  }
});

test('a client’s assistant looks things up in their own cases and offers no drafts', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await openAssistant(s.client);
    await say(s.client, 'What is the status of my cases?');
    const reply = s.client.locator('.card.a').last();
    await expect(reply.getByRole('listitem').first()).toContainText('Looked up your cases');
    await expect(reply).toContainText('You have 1 cases.');
    await expect(reply.getByText(/ask your lawyer/i)).toBeVisible();

    await say(s.client, 'Prepare a legal notice draft for me');
    const refused = s.client.locator('.card.a').last();
    await expect(refused).toContainText('I cannot create drafts');
    await expect(refused.getByRole('group', { name: 'Proposed action' })).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('administrators use the Knowledge Assistant but not the agent', async ({ browser }) => {
  const { newAdminPage } = await import('./support/helpers');
  const admin = await newAdminPage(browser);
  try {
    await admin.page.goto('/ask');
    await expect(admin.page.getByRole('heading', { name: 'Knowledge Assistant', level: 1 })).toBeVisible();
    await expect(admin.page.getByRole('button', { name: 'Assistant', exact: true })).toBeDisabled();
    const status = await admin.page.request.get('/api/v1/assistant/status');
    expect((await status.json()).assistant).toBe(false);
    expect((await admin.page.request.post('/api/v1/assistant/requests', { data: { text: 'hello' } })).status()).toBe(403);
  } finally {
    await admin.close();
  }
});
