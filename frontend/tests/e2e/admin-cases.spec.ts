import { expect, test } from './support/test';
import { createClientScenario, newAdminPage } from './support/helpers';

const pdf = (name: string) => ({ name, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 secret') });

type AuditRow = { action: string; target_id: string | null; detail: Record<string, unknown> };

async function auditFor(admin: import('@playwright/test').Page, match: (row: AuditRow) => boolean): Promise<AuditRow[]> {
  const body = await (await admin.request.get('/api/v1/admin/audit?limit=200')).json();
  return (body.items as AuditRow[]).filter(match);
}

test('the case list shows every case with its advocate and number of clients, and can be searched', async ({ browser }) => {
  const admin = await newAdminPage(browser);
  try {
    const page = admin.page;
    await page.getByRole('link', { name: 'Cases', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Cases', level: 1 })).toBeVisible();
    const row = page.locator('tbody tr', { hasText: 'Sharma v. Verma Traders' });
    await expect(row).toContainText('Adv. Rohan Sharma');
    await expect(page.locator('tbody tr', { hasText: 'Gupta v. Gupta Estate' })).toContainText('Closed');

    await page.getByLabel('Search cases').fill('imran');
    await expect(page.locator('tbody tr')).toHaveCount(1);
    await page.getByLabel('Search cases').fill('no such case');
    await expect(page.getByText('No cases match.')).toBeVisible();
  } finally {
    await admin.close();
  }
});

test('listing and searching cases is not recorded, but opening one is', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page); // a case of this test's own, so parallel runs cannot interfere
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    const mine = (row: AuditRow) => row.target_id === s.caseId;

    await a.getByRole('link', { name: 'Cases', exact: true }).click();
    await a.getByLabel('Search cases').fill(s.caseTitle);
    await expect(a.locator('tbody tr')).toHaveCount(1);
    expect(await auditFor(a, mine)).toHaveLength(0); // listing and searching wrote nothing about this case

    await a.locator('tbody tr', { hasText: s.caseTitle }).click();
    await expect(a.getByRole('heading', { name: s.caseTitle, level: 1 })).toBeVisible();
    const entries = await auditFor(a, mine);
    expect(entries).toHaveLength(1); // exactly one entry for one visit
    expect(entries[0].action).toBe('case.view');
  } finally {
    await admin.close();
    await s.close();
  }
});

test('the administrator sees private notes, internal documents and clients’ messages, and is told it is recorded', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const marker = `ZZ-${Date.now()}`;
    const api = s.advocate.request;
    await api.patch(`/api/v1/cases/${s.caseId}`, { data: { notes: `Private notes ${marker}` } });
    await api.post(`/api/v1/cases/${s.caseId}/timeline`, { data: { text: `Private timeline note ${marker}` } });
    const upload = await api.post(`/api/v1/cases/${s.caseId}/documents`, { multipart: { file: pdf(`internal-${marker}.pdf`) } });
    expect(upload.ok()).toBeTruthy();
    await s.client.request.post(`/api/v1/client/cases/${s.caseId}/questions`, { data: { kind: 'question', text: `Client question ${marker}` } });

    const a = admin.page;
    await a.getByRole('link', { name: 'Cases', exact: true }).click();
    await a.getByLabel('Search cases').fill(s.caseTitle);
    await a.locator('tbody tr', { hasText: s.caseTitle }).click();

    await expect(a.getByRole('heading', { name: s.caseTitle, level: 1 })).toBeVisible();
    await expect(a.getByRole('note')).toContainText('Opening it is recorded in the audit log');
    await expect(a.getByText(`Private notes ${marker}`)).toBeVisible();
    const timelineRow = a.locator('.act', { hasText: `Private timeline note ${marker}` });
    await expect(timelineRow.getByText('Private', { exact: true })).toBeVisible();
    const docRow = a.locator('.act', { hasText: `internal-${marker}.pdf` });
    await expect(docRow.getByText('Private', { exact: true })).toBeVisible();
    await expect(docRow).toContainText('download is recorded');
    await expect(a.locator('.act', { hasText: `Client question ${marker}` })).toContainText('Test Client');
    await expect(a.getByText('Clients on this case')).toBeVisible();
  } finally {
    await admin.close();
    await s.close();
  }
});

test('the case view is read-only', async ({ browser }) => {
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    await a.goto('/admin/cases');
    await a.locator('tbody tr', { hasText: 'Sharma v. Verma Traders' }).click();
    await expect(a.getByRole('heading', { name: 'Sharma v. Verma Traders', level: 1 })).toBeVisible();
    const main = a.locator('main');
    await expect(main.getByRole('button')).toHaveCount(0);
    await expect(main.getByRole('textbox')).toHaveCount(0);
    await expect(main.getByRole('link', { name: /edit|delete|reassign|close case/i })).toHaveCount(0);
  } finally {
    await admin.close();
  }
});

test('downloading a document works and is recorded', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const admin = await newAdminPage(browser);
  try {
    const name = `evidence-${Date.now()}.pdf`;
    const upload = await s.advocate.request.post(`/api/v1/cases/${s.caseId}/documents`, { multipart: { file: pdf(name) } });
    const documentId = (await upload.json()).id as string;

    const a = admin.page;
    const mine = (row: AuditRow) => row.action === 'document.download' && row.detail.file_name === name;
    expect(await auditFor(a, mine)).toHaveLength(0);
    const response = await a.request.get(`/api/v1/admin/cases/${s.caseId}/documents/${documentId}/download`);
    expect(response.status()).toBe(200);
    expect((await response.body()).toString()).toContain('%PDF');
    expect(await auditFor(a, mine)).toHaveLength(1);

    await a.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Audit log' }).click();
    await expect(a.locator('#admin-audit .act', { hasText: name })).toContainText('Downloaded a case document');
  } finally {
    await admin.close();
    await s.close();
  }
});

test('a case that does not exist says so', async ({ browser }) => {
  const admin = await newAdminPage(browser);
  try {
    await admin.page.goto('/admin/cases/00000000-0000-0000-0000-000000000000');
    await expect(admin.page.getByRole('heading', { name: 'Case not found' })).toBeVisible();
  } finally {
    await admin.close();
  }
});

test('advocates and clients cannot open the case view or its data', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    for (const who of [s.advocate, s.client]) {
      expect((await who.request.get(`/api/v1/admin/cases/${s.caseId}`)).status()).toBe(403);
      expect((await who.request.get('/api/v1/admin/cases')).status()).toBe(403);
      await who.goto(`/admin/cases/${s.caseId}`);
      await expect(who.getByText('This page is for administrators only.')).toBeVisible();
    }
  } finally {
    await s.close();
  }
});
