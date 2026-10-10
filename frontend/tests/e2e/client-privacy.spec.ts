import { expect, test } from './support/test';
import { createClientScenario } from './support/helpers';

const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 test') });

test('what the advocate shares appears for the client, and nothing else does', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const marker = `INTERNAL-${Date.now()}`;

    // The advocate has an internal document and a private note; neither is shared.
    const upload = await s.advocate.request.post(`/api/v1/cases/${s.caseId}/documents`, {
      multipart: { file: pdf(`${marker}.pdf`) },
    });
    expect(upload.ok()).toBeTruthy();
    const note = await s.advocate.request.post(`/api/v1/cases/${s.caseId}/timeline`, {
      data: { text: `Private note ${marker}` },
    });
    expect(note.ok()).toBeTruthy();

    // The client sees neither, anywhere on the case page.
    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByRole('heading', { level: 1 })).toHaveText(s.caseTitle);
    await expect(s.client.getByText('Your lawyer has not shared any documents yet.')).toBeVisible();
    expect(await s.client.locator('main').innerText()).not.toContain(marker);

    // The advocate sets a status and writes an update, through the real screens.
    await s.advocate.goto(`/cases/${s.caseId}`);
    await s.advocate.getByRole('tab', { name: 'Client view' }).click();
    await s.advocate.getByLabel('Client-facing status').selectOption('awaiting_order');
    await s.advocate.getByRole('button', { name: 'Update status' }).click();
    await expect(s.advocate.getByText('Status updated. Clients have been told.')).toBeVisible();
    await s.advocate.getByLabel('Short update, in plain language').fill('The court has reserved its order.');
    await s.advocate.getByRole('button', { name: 'Send update' }).click();
    await expect(s.advocate.getByText('Update sent. Clients have been told.')).toBeVisible();

    // The advocate's timeline marks the private note as private.
    const privateRow = s.advocate.locator('.tl li', { hasText: `Private note ${marker}` });
    await expect(privateRow.getByText('Private', { exact: true })).toBeVisible();

    // The client now sees the status and the update, but still not the private items.
    await s.client.reload();
    await expect(s.client.getByText('Awaiting order').first()).toBeVisible();
    await expect(s.client.getByText('The court has reserved its order.')).toBeVisible();
    await expect(s.client.getByText('Status changed to Awaiting order.')).toBeVisible();
    expect(await s.client.locator('main').innerText()).not.toContain(marker);
  } finally {
    await s.close();
  }
});

test('sharing a document shows it to the client; unsharing removes it and its link', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const name = `Notice-${Date.now()}.pdf`;
    const upload = await s.advocate.request.post(`/api/v1/cases/${s.caseId}/documents`, {
      multipart: { file: pdf(name) },
    });
    const documentId = (await upload.json()).id as string;

    await s.advocate.goto(`/cases/${s.caseId}`);
    const share = s.advocate.getByRole('button', { name: `Share with client: ${name}` });
    await expect(share).toHaveAttribute('aria-pressed', 'false');
    await share.click();
    await expect(s.advocate.getByRole('button', { name: `Shared with client: ${name}` })).toHaveAttribute('aria-pressed', 'true');

    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByText(name).first()).toBeVisible();
    const link = `/api/v1/client/cases/${s.caseId}/documents/${documentId}/download`;
    expect((await s.client.request.get(link)).status()).toBe(200);

    await s.advocate.getByRole('button', { name: `Shared with client: ${name}` }).click();
    await expect(s.advocate.getByRole('button', { name: `Share with client: ${name}` })).toHaveAttribute('aria-pressed', 'false');

    await s.client.reload();
    await expect(s.client.getByText('Your lawyer has not shared any documents yet.')).toBeVisible();
    expect((await s.client.request.get(link)).status()).toBe(404);
  } finally {
    await s.close();
  }
});

test('a hearing outcome is private until the advocate shares it', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const yesterday = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    const created = await s.advocate.request.post(`/api/v1/cases/${s.caseId}/hearings`, {
      data: { scheduled_at: yesterday, purpose: 'Evidence' },
    });
    expect(created.ok()).toBeTruthy();

    await s.advocate.goto(`/cases/${s.caseId}`);
    await s.advocate.getByRole('tab', { name: 'Hearings' }).click();
    await s.advocate.getByRole('button', { name: 'Record outcome' }).click();
    await s.advocate.getByLabel('What happened at this hearing').fill('Witness examined; cross-examination next.');
    await s.advocate.getByRole('button', { name: 'Save outcome' }).click();
    await expect(s.advocate.getByText('Outcome: Witness examined; cross-examination next.')).toBeVisible();
    await expect(s.advocate.getByText('Private', { exact: true }).first()).toBeVisible();

    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByRole('heading', { name: 'Hearings' })).toBeVisible();
    expect(await s.client.locator('main').innerText()).not.toContain('Witness examined');

    await s.advocate.getByRole('button', { name: 'Edit outcome' }).click();
    await s.advocate.getByLabel('Share this outcome with clients').check();
    await s.advocate.getByRole('button', { name: 'Save outcome' }).click();
    await expect(s.advocate.getByText('Visible to clients').first()).toBeVisible();

    await s.client.reload();
    await expect(s.client.getByText('Outcome: Witness examined; cross-examination next.')).toBeVisible();
  } finally {
    await s.close();
  }
});

test('status changes and hearing dates cannot be hidden from the client', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.advocate.request.put(`/api/v1/cases/${s.caseId}/client-status`, { data: { status: 'notice_stage' } });
    const next = new Date(Date.now() + 5 * 24 * 3600 * 1000).toISOString();
    await s.advocate.request.post(`/api/v1/cases/${s.caseId}/hearings`, { data: { scheduled_at: next, purpose: 'Arguments' } });

    await s.advocate.goto(`/cases/${s.caseId}`);
    await s.advocate.getByRole('tab', { name: 'Client view' }).click();
    const statusRow = s.advocate.locator('.tl li', { hasText: 'Status changed to Notice stage.' });
    await expect(statusRow.getByText('Visible to clients')).toBeVisible();
    await expect(statusRow.getByRole('button')).toHaveCount(0); // no way to hide it

    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByText('Notice stage').first()).toBeVisible();
    await expect(s.client.getByText(/Hearing scheduled for/)).toBeVisible();
  } finally {
    await s.close();
  }
});

test('the advocate can set what clients see about them', async ({ page }) => {
  const { newAdvocateWithCase } = await import('./support/helpers');
  await newAdvocateWithCase(page);
  await page.goto('/settings');
  await page.getByLabel('Phone', { exact: true }).fill('+91 98765 43210');
  await page.getByRole('button', { name: 'Save contact details' }).click();
  await expect(page.getByText('Saved. Clients see only the fields you have filled in.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Phone', { exact: true })).toHaveValue('+91 98765 43210');
});
