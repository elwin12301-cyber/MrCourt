import { expect, test } from './support/test';
import { addClient, createClientScenario, signInAs } from './support/helpers';

const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 test') });

test('a change the advocate makes appears for the client without reloading', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.client.goto('/dashboard');
    await expect(s.client.locator('.clientcase')).toBeVisible();
    // Nothing yet: no unread badge on the Updates link.
    await expect(s.client.getByRole('link', { name: 'Updates', exact: true })).toBeVisible();

    await s.advocate.request.put(`/api/v1/cases/${s.caseId}/client-status`, { data: { status: 'awaiting_order' } });

    // The page is not reloaded; the periodic refresh brings the badge in (3 seconds in tests).
    await expect(s.client.getByRole('link', { name: 'Updates, 1 unread' })).toBeVisible({ timeout: 15_000 });
    await expect(s.client.locator('.nav .badge')).toHaveText('1');

    await s.client.getByRole('link', { name: 'Updates, 1 unread' }).click();
    await expect(s.client.getByRole('heading', { name: 'Updates', level: 1 })).toBeVisible();
    await expect(s.client.getByText('1 unread')).toBeVisible();
    const row = s.client.locator('.updaterow').first();
    await expect(row).toContainText('The status changed to Awaiting order.');
    await expect(row).toContainText('New'); // not colour alone

    // Opening the update takes the client to the case and clears it.
    await row.click();
    await expect(s.client.getByRole('heading', { level: 1 })).toHaveText(s.caseTitle);
    await expect(s.client.getByRole('link', { name: 'Updates', exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(s.client.locator('.nav .badge')).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('each kind of change produces a notice, and unsharing produces none', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const api = s.advocate.request;
    await api.put(`/api/v1/cases/${s.caseId}/client-status`, { data: { status: 'hearing_scheduled' } });
    const created = await api.post(`/api/v1/cases/${s.caseId}/hearings`, {
      data: { scheduled_at: new Date(Date.now() - 86_400_000).toISOString(), purpose: 'Evidence' },
    });
    const hearingId = (await created.json()).id as string;
    await api.patch(`/api/v1/cases/${s.caseId}/hearings/${hearingId}`, {
      data: { scheduled_at: new Date(Date.now() - 2 * 86_400_000).toISOString() },
    });
    await api.put(`/api/v1/cases/${s.caseId}/hearings/${hearingId}/outcome`, { data: { outcome: 'Heard.', shared: true } });
    const doc = await api.post(`/api/v1/cases/${s.caseId}/documents`, { multipart: { file: pdf('notice.pdf') } });
    const docId = (await doc.json()).id as string;
    await api.put(`/api/v1/cases/${s.caseId}/documents/${docId}/sharing`, { data: { shared: true } });
    await api.post(`/api/v1/cases/${s.caseId}/client-updates`, { data: { message: 'Please call the office.' } });

    await s.client.goto('/updates');
    const list = s.client.locator('.updaterow');
    await expect(list).toHaveCount(6);
    const text = await s.client.locator('main').innerText();
    for (const expected of [
      'The status changed to Hearing scheduled.',
      'A hearing was scheduled for',
      'A hearing was moved to',
      'A hearing outcome was shared with you.',
      'A document was shared with you.',
      'Your lawyer posted an update: Please call the office.',
    ]) {
      expect(text).toContain(expected);
    }
    // The notice about the document does not give away the file name.
    expect(text).not.toContain('notice.pdf');

    // Unsharing the document changes what the client can see, but sends nothing new.
    await api.put(`/api/v1/cases/${s.caseId}/documents/${docId}/sharing`, { data: { shared: false } });
    await s.client.reload();
    await expect(s.client.locator('.updaterow')).toHaveCount(6);
  } finally {
    await s.close();
  }
});

test('mark all as read', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    for (const message of ['First.', 'Second.', 'Third.']) {
      await s.advocate.request.post(`/api/v1/cases/${s.caseId}/client-updates`, { data: { message } });
    }
    await s.client.goto('/updates');
    await expect(s.client.getByText('3 unread')).toBeVisible();
    await s.client.getByRole('button', { name: 'Mark all as read' }).click();
    await expect(s.client.getByText('You are up to date')).toBeVisible();
    await expect(s.client.getByRole('button', { name: 'Mark all as read' })).toBeDisabled();
    await expect(s.client.locator('.updaterow .badge')).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('each client has their own unread count', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const second = await addClient(browser, s);
  try {
    await s.advocate.request.post(`/api/v1/cases/${s.caseId}/client-updates`, { data: { message: 'For both of you.' } });

    await s.client.goto('/updates');
    await expect(s.client.getByText('1 unread')).toBeVisible();
    await s.client.getByRole('button', { name: 'Mark all as read' }).click();
    await expect(s.client.getByText('You are up to date')).toBeVisible();

    await second.page.goto('/updates');
    await expect(second.page.getByText('1 unread')).toBeVisible(); // untouched by the first client
  } finally {
    await second.close();
    await s.close();
  }
});

test('a removed client no longer sees the case or its updates', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.advocate.request.post(`/api/v1/cases/${s.caseId}/client-updates`, { data: { message: 'Soon removed.' } });
    await s.client.goto('/updates');
    await expect(s.client.locator('.updaterow')).toHaveCount(1);

    const invitations = await (await s.advocate.request.get(`/api/v1/cases/${s.caseId}/invitations`)).json();
    await s.advocate.request.delete(`/api/v1/cases/${s.caseId}/invitations/${invitations[0].id}`);

    await s.client.reload();
    await expect(s.client.getByText(/Nothing yet/)).toBeVisible();
    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByRole('heading', { name: 'Case not found' })).toBeVisible();
  } finally {
    await s.close();
  }
});

test('the dashboard shows the latest updates and links to all of them', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  const card = page.locator('#latest-updates');
  await expect(card).toBeVisible();
  await expect(card).toContainText('Your next hearing is for evidence');
  await card.getByRole('link', { name: 'See all' }).click();
  await expect(page.getByRole('heading', { name: 'Updates', level: 1 })).toBeVisible();
});

test('advocates have no Updates page', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible(); // signed in
  await expect(page.getByRole('link', { name: 'Updates' })).toHaveCount(0);
  await page.goto('/updates');
  await expect(page).toHaveURL(/\/dashboard$/);
});
