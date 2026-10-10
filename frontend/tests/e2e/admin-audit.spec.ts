import { expect, test } from './support/test';
import { newAdminPage, newPerson } from './support/helpers';

test('every admin action appears in the audit log, newest first, with who and what', async ({ browser }) => {
  const person = await newPerson(browser, 'petitioner');
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    const unique = `Audited ${Date.now()}-${Math.floor(Math.random() * 1e6)}`; // this run's own name
    const people = await (await a.request.get(`/api/v1/admin/users?role=petitioner&q=${encodeURIComponent(person.email)}`)).json();
    const id = people[0].id as string;

    expect((await a.request.patch(`/api/v1/admin/users/${id}`, { data: { full_name: unique } })).ok()).toBeTruthy();
    expect((await a.request.post(`/api/v1/admin/users/${id}/suspend`, { data: { reason: 'Audit test' } })).ok()).toBeTruthy();
    expect((await a.request.post(`/api/v1/admin/users/${id}/reactivate`)).ok()).toBeTruthy();
    expect((await a.request.post(`/api/v1/admin/users/${id}/sign-out`)).ok()).toBeTruthy();

    await a.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Audit log' }).click();
    await expect(a.getByRole('heading', { name: 'Audit log', level: 1 })).toBeVisible();

    // Only this person's entries (other runs write to the same log at the same time).
    const rows = a.locator('#admin-audit .act', { hasText: unique });
    await expect(rows).toHaveCount(4);
    const texts = await rows.allInnerTexts();
    expect(texts[0]).toContain('Site Administrator · Forced a sign-out');
    expect(texts[1]).toContain('Reactivated an account');
    expect(texts[2]).toContain('Suspended an account');
    expect(texts[2]).toContain('Reason: Audit test');
    expect(texts[3]).toContain("Corrected a person's details");
    expect(texts[3]).toContain('Changed: full name');
  } finally {
    await admin.close();
    await person.close();
  }
});

test('the log records that contact details changed, but not the details themselves', async ({ browser }) => {
  const person = await newPerson(browser, 'petitioner');
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    const people = await (await a.request.get(`/api/v1/admin/users?role=petitioner&q=${encodeURIComponent(person.email)}`)).json();
    const newEmail = `private-new-${Date.now()}@example.com`;
    await a.request.patch(`/api/v1/admin/users/${people[0].id}`, { data: { email: newEmail } });

    await a.goto('/admin/audit');
    const row = a.locator('#admin-audit .act', { hasText: person.name });
    await expect(row.first()).toContainText('Changed: email');
    const text = await a.locator('#admin-audit').innerText();
    expect(text).not.toContain(newEmail);
    expect(text).not.toContain(person.email);
  } finally {
    await admin.close();
    await person.close();
  }
});

test('the log has no controls to change or remove entries', async ({ browser }) => {
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    await a.goto('/admin/audit');
    await expect(a.getByRole('heading', { name: 'Audit log', level: 1 })).toBeVisible();
    await expect(a.locator('#admin-audit').getByRole('textbox')).toHaveCount(0);
    await expect(a.locator('#admin-audit').getByRole('button', { name: /edit|delete|remove|clear/i })).toHaveCount(0);
    expect((await a.request.delete('/api/v1/admin/audit')).status()).toBe(405);
    expect((await a.request.put('/api/v1/admin/audit', { data: {} })).status()).toBe(405);
  } finally {
    await admin.close();
  }
});

test('the overview shows the latest entries and links to the full log', async ({ browser }) => {
  const person = await newPerson(browser, 'petitioner');
  const admin = await newAdminPage(browser);
  try {
    const a = admin.page;
    const people = await (await a.request.get(`/api/v1/admin/users?role=petitioner&q=${encodeURIComponent(person.email)}`)).json();
    await a.request.post(`/api/v1/admin/users/${people[0].id}/sign-out`);
    await a.goto('/dashboard');
    const rows = a.locator('#admin-overview .act');
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeLessThanOrEqual(5);
    await expect(rows.first()).toContainText(' · ');
    await a.locator('#admin-overview').getByRole('link', { name: 'Audit log' }).click();
    await expect(a).toHaveURL(/\/admin\/audit$/);
  } finally {
    await admin.close();
    await person.close();
  }
});

test('the log is closed to advocates and clients', async ({ browser }) => {
  const advocate = await newPerson(browser, 'advocate');
  try {
    await advocate.page.request.post('/api/v1/auth/login', { data: { identifier: advocate.email, password: advocate.password } });
    expect((await advocate.page.request.get('/api/v1/admin/audit')).status()).toBe(403);
    await advocate.page.goto('/admin/audit');
    await expect(advocate.page.getByText('This page is for administrators only.')).toBeVisible();
  } finally {
    await advocate.close();
  }
});
