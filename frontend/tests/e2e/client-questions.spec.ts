import { expect, test } from './support/test';
import { addClient, createClientScenario, signInAs } from './support/helpers';

test('the client sees who their lawyer is, with only the details the lawyer shared', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await page.locator('.clientcase').click();
  const card = page.locator('.card', { has: page.getByRole('heading', { name: 'My lawyer' }) });
  await expect(card).toContainText('Adv. Rohan Sharma');
  await expect(card).toContainText('Bar Council verified');
  await expect(card.getByRole('link', { name: '+91 98100 12345' })).toHaveAttribute('href', 'tel:+919810012345');
  await expect(card).toContainText('Chamber 14, Saket Courts, New Delhi');
  await expect(card.getByText('Email')).toHaveCount(0); // the advocate left email blank
});

test('an earlier question and its reply are shown', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await page.locator('.clientcase').click();
  const box = page.locator('#ask-lawyer');
  await expect(box).toContainText('When can I expect the court to decide?');
  await expect(box).toContainText('After evidence and arguments');
});

test('ask, reply and read: the whole conversation', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.client.goto(`/cases/${s.caseId}`);
    const box = s.client.locator('#ask-lawyer');
    await expect(box.getByRole('button', { name: 'Send question' })).toBeDisabled();
    await box.getByLabel('Your question').fill('What documents should I bring?');
    await box.getByRole('button', { name: 'Send question' }).click();
    await expect(box.getByText('Sent to your lawyer.')).toBeVisible();
    await expect(box).toContainText('What documents should I bring?');
    await expect(box.getByText('Sent', { exact: true })).toBeVisible(); // no promised response time
    await expect(box).not.toContainText('within');

    // The advocate answers from the Client view tab.
    await s.advocate.goto(`/cases/${s.caseId}`);
    await s.advocate.getByRole('tab', { name: 'Client view' }).click();
    const inbox = s.advocate.locator('#client-questions');
    await expect(inbox).toContainText('Test Client');
    await expect(inbox).toContainText('What documents should I bring?');
    await expect(inbox.getByText('1 waiting')).toBeVisible();
    await inbox.getByLabel('Reply to Test Client').fill('Please bring your ID and the original cheque.');
    await inbox.getByRole('button', { name: 'Send reply' }).click();
    await expect(inbox.getByText('Your reply')).toBeVisible();

    // The client sees the reply, labelled new.
    await s.client.reload();
    await expect(s.client.locator('#ask-lawyer')).toContainText('Please bring your ID and the original cheque.');
    await expect(s.client.locator('#ask-lawyer').getByText('New', { exact: true })).toBeVisible();
  } finally {
    await s.close();
  }
});

test('asking for an update needs no typing', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.client.goto(`/cases/${s.caseId}`);
    await s.client.getByRole('button', { name: 'Ask for an update' }).click();
    await expect(s.client.getByText('Update requested.')).toBeVisible();
    await expect(s.client.locator('#ask-lawyer')).toContainText('You asked for an update');
  } finally {
    await s.close();
  }
});

test('two clients on one case never see each other’s messages', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  const second = await addClient(browser, s, 'Second Client');
  try {
    await s.client.goto(`/cases/${s.caseId}`);
    await s.client.getByLabel('Your question').fill('FIRST-CLIENT: when is the next date?');
    await s.client.getByRole('button', { name: 'Send question' }).click();
    await expect(s.client.locator('#ask-lawyer')).toContainText('FIRST-CLIENT');

    await second.page.goto(`/cases/${s.caseId}`);
    await second.page.getByLabel('Your question').fill('SECOND-CLIENT: can I pay in instalments?');
    await second.page.getByRole('button', { name: 'Send question' }).click();
    await expect(second.page.locator('#ask-lawyer')).toContainText('SECOND-CLIENT');

    // Each sees only their own.
    expect(await s.client.locator('main').innerText()).not.toContain('SECOND-CLIENT');
    await second.page.reload();
    expect(await second.page.locator('main').innerText()).not.toContain('FIRST-CLIENT');

    // The advocate sees both, with names.
    await s.advocate.goto(`/cases/${s.caseId}`);
    await s.advocate.getByRole('tab', { name: 'Client view' }).click();
    const inbox = s.advocate.locator('#client-questions');
    await expect(inbox).toContainText('FIRST-CLIENT');
    await expect(inbox).toContainText('SECOND-CLIENT');
    await expect(inbox.getByText('2 waiting')).toBeVisible();

    // Reply to the second client only.
    const replyForm = inbox.locator('form', { has: s.advocate.getByLabel('Reply to Second Client') });
    await replyForm.getByLabel('Reply to Second Client').fill('Yes, instalments are possible.');
    await replyForm.getByRole('button', { name: 'Send reply' }).click();
    await s.client.reload();
    expect(await s.client.locator('main').innerText()).not.toContain('instalments are possible');
    await second.page.reload();
    await expect(second.page.locator('#ask-lawyer')).toContainText('Yes, instalments are possible.');
  } finally {
    await second.close();
    await s.close();
  }
});

test('when the lawyer is no longer on MrCourt, the client is told and cannot send', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    const gone = await s.advocate.request.post('/api/v1/me/deactivate', { data: { acknowledge_case_retention: true } });
    expect(gone.ok()).toBeTruthy();
    await s.client.goto(`/cases/${s.caseId}`);
    await expect(s.client.getByText('Your lawyer is no longer available on MrCourt. Please contact them directly.')).toBeVisible();
    await expect(s.client.getByRole('button', { name: 'Send question' })).toHaveCount(0);
  } finally {
    await s.close();
  }
});

test('the dashboard shows the lawyer too', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await expect(page.getByRole('heading', { name: 'My lawyer' })).toBeVisible();
  await expect(page.getByText('Bar Council verified')).toBeVisible();
});
