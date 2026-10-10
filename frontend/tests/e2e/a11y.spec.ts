import { expect, test } from './support/test';
import { createClientScenario, expectNoA11yViolations, newAdvocateWithCase, setTheme, signInAs, type ThemeName } from './support/helpers';

const THEMES: ThemeName[] = ['light', 'dark'];

async function scanBoth(page: import('@playwright/test').Page, ready: () => Promise<void>) {
  for (const theme of THEMES) {
    await setTheme(page, theme);
    await ready();
    await expectNoA11yViolations(page);
  }
}

test.describe('public screens', () => {
  test('welcome', async ({ page }) => {
    await page.goto('/');
    await scanBoth(page, () => expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible());
  });

  test('sign in', async ({ page }) => {
    await page.goto('/login');
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible());
  });

  test('create account', async ({ page }) => {
    await page.goto('/register');
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible());
  });

  test('petitioner sign in', async ({ page }) => {
    await page.goto('/login/petitioner');
    await scanBoth(page, () => expect(page.getByText('Petitioner sign in', { exact: true })).toBeVisible());
  });

  test('petitioner create account', async ({ page }) => {
    await page.goto('/register/petitioner');
    await scanBoth(page, () => expect(page.getByText('Petitioner sign up', { exact: true })).toBeVisible());
  });
});

test.describe('advocate screens', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  });

  test('dashboard', async ({ page }) => {
    await scanBoth(page, () => expect(page.locator('.hear').first()).toBeVisible());
  });

  test('cases', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await scanBoth(page, () => expect(page.locator('#caseRows tr').first()).toBeVisible());
  });

  test('case detail, every tab', async ({ page }) => {
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.locator('#caseRows tr', { hasText: 'Sharma v. Verma Traders' }).click();
    for (const tab of ['Overview', 'Hearings', 'Documents', 'Notes']) {
      await page.getByRole('tab', { name: tab }).click();
      await scanBoth(page, () => expect(page.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true'));
    }
  });

  test('ask MrCourt with a cited and an uncited answer', async ({ page }) => {
    await page.getByRole('link', { name: 'Ask MrCourt' }).click();
    await page.getByRole('button', { name: 'Cheque bounce, S.138' }).click();
    await expect(page.locator('.src').first()).toBeVisible();
    await page.getByLabel('Ask a legal question').fill('How do I register a trademark in India?');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.locator('.card.a').last()).toContainText('could not find a reliable source');
    await scanBoth(page, () => expect(page.locator('.card.a')).toHaveCount(2));
  });

  test('drafts, reading and editing', async ({ page }) => {
    await page.getByRole('link', { name: 'Drafts' }).click();
    await scanBoth(page, () => expect(page.locator('#dTitle')).toBeVisible());
    await page.getByRole('button', { name: 'Export', exact: true }).click();
    await scanBoth(page, () => expect(page.getByRole('group', { name: 'Export format' })).toBeVisible());
  });

  test('settings with the privacy panel open', async ({ page }) => {
    await page.getByRole('link', { name: 'Settings' }).click();
    await page.getByRole('button', { name: 'Manage' }).click();
    await scanBoth(page, () => expect(page.getByRole('button', { name: 'Download my data' })).toBeVisible());
  });

  test('deactivation dialog', async ({ page }) => {
    await newAdvocateWithCase(page); // a throwaway account; the dialog is only opened, never confirmed
    await page.goto('/settings');
    await page.getByRole('button', { name: 'Manage' }).click();
    await page.getByRole('button', { name: 'Deactivate account' }).click();
    await scanBoth(page, () => expect(page.getByRole('dialog')).toBeVisible());
  });
});

test('petitioner dashboard with an invitation', async ({ page }) => {
  await signInAs(page, 'anita.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await scanBoth(page, () => expect(page.getByRole('heading', { level: 1 })).toBeVisible());
});

test('administrator verifications', async ({ page }) => {
  await signInAs(page, 'admin@example.com');
  await page.getByRole('link', { name: 'Verifications' }).click();
  await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Verifications' })).toBeVisible());
});


test.describe('client screens', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'anita.sharma@example.com');
    await expect(page.locator('.clientcase')).toBeVisible();
  });

  test('client dashboard with latest updates and the lawyer card', async ({ page }) => {
    await scanBoth(page, () => expect(page.locator('#latest-updates')).toBeVisible());
  });

  test('my cases', async ({ page }) => {
    await page.getByRole('link', { name: 'My cases' }).click();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'My cases', level: 1 })).toBeVisible());
  });

  test('client case page: status, hearing description, timeline, lawyer, questions and access', async ({ page }) => {
    await page.locator('.clientcase').click();
    await expect(page.locator('.hearingdesc')).toBeVisible();
    await page.getByText('What does “Hearing” mean?').click();
    await scanBoth(page, () => expect(page.locator('#who-can-see')).toBeVisible());
  });

  test('updates', async ({ page }) => {
    await page.getByRole('link', { name: /^Updates/ }).click();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Updates', level: 1 })).toBeVisible());
  });

  test('ask MrCourt with the ask-your-lawyer notice', async ({ page }) => {
    await page.getByRole('link', { name: 'Ask MrCourt' }).click();
    await page.getByLabel('Ask a legal question').fill('Should I accept the settlement offer in my case?');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.locator('.advicenotice')).toBeVisible();
    await scanBoth(page, () => expect(page.locator('.advicenotice')).toBeVisible());
  });
});

test('client screens before anything is shared (empty states)', async ({ browser, page }) => {
  const s = await createClientScenario(browser, page);
  try {
    await s.client.goto('/dashboard');
    await expect(s.client.locator('.clientcase')).toBeVisible();
    await scanBoth(s.client, () => expect(s.client.locator('.clientcase')).toBeVisible());
    await s.client.locator('.clientcase').click();
    await scanBoth(s.client, () => expect(s.client.getByText('Nothing has been shared yet.')).toBeVisible());
  } finally {
    await s.close();
  }
});

test.describe('advocate client controls', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await page.getByRole('link', { name: 'Cases' }).click();
    await page.locator('#caseRows tr', { hasText: 'Sharma v. Verma Traders' }).click();
  });

  test('the Client view tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Client view' }).click();
    await expect(page.locator('#client-questions')).toBeVisible();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Case timeline' })).toBeVisible());
  });

  test('hearings with outcome controls, and documents with share controls', async ({ page }) => {
    await page.getByRole('tab', { name: 'Hearings' }).click();
    await page.getByRole('button', { name: 'Edit outcome' }).first().click();
    await scanBoth(page, () => expect(page.getByLabel('Share this outcome with clients')).toBeVisible());
    await page.getByRole('tab', { name: 'Documents' }).click();
    await scanBoth(page, () => expect(page.getByRole('button', { name: /Share with client|Shared with client/ }).first()).toBeVisible());
  });

  test('invited clients list', async ({ page }) => {
    await expect(page.getByText('Clients on this case')).toBeVisible();
    await scanBoth(page, () => expect(page.getByText('Clients on this case')).toBeVisible());
  });
});

test('the advocate contact card in settings', async ({ page }) => {
  await signInAs(page, 'rohan.sharma@example.com');
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await page.getByRole('link', { name: 'Settings' }).click();
  await scanBoth(page, () => expect(page.getByRole('heading', { name: 'What clients see about you' })).toBeVisible());
});

test('administrator sign in', async ({ page }) => {
  await page.goto('/login/admin');
  await scanBoth(page, () => expect(page.getByText('Administrator sign in', { exact: true })).toBeVisible());
});

test.describe('administrator screens', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'admin@example.com');
    await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
  });

  test('overview', async ({ page }) => {
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Latest activity' })).toBeVisible());
  });

  test('advocates and clients lists', async ({ page }) => {
    await page.goto('/admin/advocates');
    await scanBoth(page, () => expect(page.locator('tbody tr').first()).toBeVisible());
    await page.goto('/admin/clients');
    await scanBoth(page, () => expect(page.locator('tbody tr').first()).toBeVisible());
  });

  test('a person’s page, with the account and cases cards', async ({ page }) => {
    await page.goto('/admin/advocates');
    await page.locator('tbody tr', { hasText: 'Adv. Rohan Sharma' }).click();
    await expect(page.getByRole('heading', { name: 'Adv. Rohan Sharma', level: 1 })).toBeVisible();
    await scanBoth(page, () => expect(page.getByRole('button', { name: 'Suspend account' })).toBeVisible());
  });

  test('cases list and the full case view', async ({ page }) => {
    await page.goto('/admin/cases');
    await scanBoth(page, () => expect(page.locator('tbody tr').first()).toBeVisible());
    await page.locator('tbody tr', { hasText: 'Sharma v. Verma Traders' }).click();
    await expect(page.getByRole('heading', { name: 'Sharma v. Verma Traders', level: 1 })).toBeVisible();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Advocate’s private notes' })).toBeVisible());
  });

  test('audit log', async ({ page }) => {
    await page.goto('/admin/audit');
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Audit log', level: 1 })).toBeVisible());
  });
});

test.describe('assistant screens', () => {
  const cheque = 'What is the punishment for cheque bounce under Section 138 of the NI Act?';

  test('ask tab: an answer, then assistant mode with steps and a proposal', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      const p = s.advocate;
      await p.goto('/ask');
      await p.getByLabel('Ask a legal question').fill(cheque);
      await p.getByRole('button', { name: 'Send' }).click();
      await scanBoth(p, () => expect(p.locator('.card.a .src').first()).toBeVisible());

      await p.getByRole('button', { name: 'Assistant', exact: true }).click();
      await p.getByLabel('Ask the assistant').fill('Prepare a legal notice draft for my case');
      await p.getByRole('button', { name: 'Send' }).click();
      await scanBoth(p, () => expect(p.getByRole('group', { name: 'Proposed action' })).toBeVisible());
    } finally {
      await s.close();
    }
  });

  test('knowledge base tab with the add form open, and the admin page', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      await s.advocate.goto('/ask/knowledge');
      await s.advocate.getByRole('button', { name: 'Add a private note' }).click();
      await scanBoth(s.advocate, () => expect(s.advocate.getByRole('form', { name: 'Add a source' })).toBeVisible());
      await s.client.goto('/ask/knowledge');
      await scanBoth(s.client, () => expect(s.client.locator('tbody tr').first()).toBeVisible());
    } finally {
      await s.close();
    }
  });

  test('history tab with a question opened', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      await s.advocate.request.post('/api/v1/questions', { data: { text: cheque, input_method: 'voice' } });
      await s.advocate.goto('/ask/history');
      const row = s.advocate.getByRole('list', { name: 'Your questions' }).getByRole('listitem').first();
      await row.getByRole('button', { name: /^Open/ }).click();
      await scanBoth(s.advocate, () => expect(row.locator('.src').first()).toBeVisible());
    } finally {
      await s.close();
    }
  });

  test('voice states: listening and blocked', async ({ page }) => {
    await page.addInitScript(() => {
      class Fake {
        lang = '';
        onerror: ((e: { error: string }) => void) | null = null;
        onend: (() => void) | null = null;
        start() {}
        stop() {
          this.onend?.();
        }
      }
      (window as unknown as Record<string, unknown>).SpeechRecognition = Fake;
    });
    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await page.goto('/ask');
    await page.getByRole('button', { name: 'Voice input' }).click();
    await scanBoth(page, () => expect(page.getByRole('status').filter({ hasText: 'Listening' })).toBeVisible());
  });

  test('administrator: knowledge base and a person’s questions', async ({ page }) => {
    await signInAs(page, 'admin@example.com');
    await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
    await page.goto('/admin/knowledge');
    await scanBoth(page, () => expect(page.locator('tbody tr').first()).toBeVisible());
    await page.goto('/admin/advocates');
    await page.locator('tbody tr', { hasText: 'Adv. Rohan Sharma' }).click();
    await page.getByRole('button', { name: 'Show questions asked' }).click();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Questions asked' })).toBeVisible());
  });
});

test.describe('complete RAG screens', () => {
  test('text assistant tab with lines', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      const p = s.advocate;
      const made = await (await p.request.post('/api/v1/text/conversations', { data: { language: 'ta-IN' } })).json();
      await p.request.post(`/api/v1/text/conversations/${made.id}/lines`, { data: { text: 'A spoken line', source: 'voice' } });
      await p.request.post(`/api/v1/text/conversations/${made.id}/lines`, { data: { text: 'A typed line', source: 'typed' } });
      await p.goto('/ask/text');
      await scanBoth(p, () => expect(p.getByRole('list', { name: 'Lines' })).toBeVisible());
    } finally {
      await s.close();
    }
  });

  test('an opened citation, and the Better for Tamil option', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      const p = s.advocate;
      await p.goto('/ask');
      await p.getByLabel(/Better for Tamil/).check();
      await p.getByLabel('Ask a legal question').fill('What is the punishment for cheque bounce under Section 138 of the NI Act?');
      await p.getByRole('button', { name: 'Send' }).click();
      const answer = p.locator('.card.a').last();
      await answer.getByRole('button', { name: 'Read source 1' }).click();
      await scanBoth(p, () => expect(answer.getByRole('region', { name: 'Source 1' })).toBeVisible());
    } finally {
      await s.close();
    }
  });

  test('history with the assistant filter and a saved conversation opened', async ({ browser, page }) => {
    const s = await createClientScenario(browser, page);
    try {
      const p = s.advocate;
      const made = await (await p.request.post('/api/v1/text/conversations', { data: { language: 'en-IN' } })).json();
      await p.request.post(`/api/v1/text/conversations/${made.id}/lines`, { data: { text: 'Saved line for the file', source: 'voice' } });
      await p.goto('/ask/history');
      const row = p.getByRole('list', { name: 'Your questions' }).getByRole('listitem').first();
      await row.getByRole('button', { name: /^Open/ }).click();
      await scanBoth(p, () => expect(row.getByRole('list', { name: 'Conversation lines' })).toBeVisible());
    } finally {
      await s.close();
    }
  });
});

test.describe('sign-up, reset and reminders screens', () => {
  test('sign-up form with the mobile number, and the code step', async ({ page }) => {
    await page.goto('/register/petitioner');
    await scanBoth(page, () => expect(page.getByLabel('Mobile number')).toBeVisible());
    const phone = `+9195${Date.now().toString().slice(-8)}`;
    await page.getByLabel('Username', { exact: true }).fill(`u${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`);
    await page.getByLabel('Full name').fill('Access Check');
    await page.getByLabel(/^Email/).fill(`access-${Date.now()}@example.com`);
    await page.getByLabel('Mobile number').fill(phone);
    await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Create account' }).click();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Verify your mobile number' })).toBeVisible());
  });

  test('forgot password: both steps', async ({ page }) => {
    await page.goto('/forgot-password');
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Forgot your password?' })).toBeVisible());
    await page.getByLabel('Email or phone').fill('nobody@example.com');
    await page.getByRole('button', { name: 'Send code' }).click();
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible());
  });

  test('the development messages page', async ({ page }) => {
    await page.goto('/dev/messages');
    await scanBoth(page, () => expect(page.getByRole('heading', { name: 'Development messages' })).toBeVisible());
  });

  test('settings with the phone number not yet verified, and the code step open', async ({ page }) => {
    const email = `phone-${Date.now()}@example.com`;
    await page.request.post('/api/v1/auth/register', {
      data: { role: 'petitioner', full_name: 'Phone Check', email, phone: `+9194${Date.now().toString().slice(-8)}`, password: 'a-strong-password' },
    });
    await page.goto('/settings');
    await expect(page.getByText('Not verified')).toBeVisible();
    await scanBoth(page, () => expect(page.getByRole('switch', { name: 'Text message reminders' })).toBeVisible());
    await page.getByRole('button', { name: 'Verify', exact: true }).click();
    await scanBoth(page, () => expect(page.getByLabel('6-digit code')).toBeVisible());
  });
});
