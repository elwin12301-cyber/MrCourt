import AxeBuilder from '@axe-core/playwright';
import { expect, type Browser, type Page } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));

/** Absolute path of the untouched prototype used as the visual source of truth. */
export const PROTOTYPE_URL = `file://${path.resolve(here, '../../../../design/MrCourt Web Prototype.html')}`;

export type ThemeName = 'light' | 'dark';

export async function setTheme(page: Page, theme: ThemeName) {
  await page.emulateMedia({ colorScheme: theme });
  await page.evaluate((t) => {
    document.documentElement.dataset.theme = t;
  }, theme);
}

/** Fails the test on any WCAG 2.1 A/AA violation, with a short readable summary. */
export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const theme = await page.evaluate(() => document.documentElement.dataset.theme ?? 'system');
  const summary = results.violations.flatMap((v) =>
    v.nodes.map((n) => {
      const data = (n.any[0]?.data ?? {}) as { fgColor?: string; bgColor?: string; contrastRatio?: number };
      const colors = data.fgColor ? ` ${data.fgColor} on ${data.bgColor} (${data.contrastRatio})` : '';
      return `[${theme}] ${v.id}${colors} :: ${n.target.join(' ')} :: ${n.html.slice(0, 80)}`;
    }),
  );
  expect(summary, `\n${summary.join('\n')}`).toEqual([]);
}

export type RoleName = 'advocate' | 'petitioner' | 'admin';

/** The sign-in page a seeded account belongs on. */
function roleOf(email: string): RoleName {
  if (email === 'admin@example.com') return 'admin';
  return /^(anita|ravi)\./.test(email) ? 'petitioner' : 'advocate';
}

/**
 * Signs in through the UI, choosing the entry that matches the account as a real person would
 * (the sign-in checks it). Pass `role` for accounts the helper cannot recognise by their email.
 */
export async function signInAs(page: Page, email: string, password = 'password123', role: RoleName = roleOf(email)) {
  await page.goto('/');
  if (role === 'admin') {
    await page.getByRole('link', { name: 'Administrator sign in' }).click();
  } else {
    await page.getByRole('button', { name: role === 'petitioner' ? "I'm a Petitioner" : "I'm an Advocate" }).click();
  }
  // Submit and wait for the answer. If the request never gets one (a rare stall when several browsers
  // share the machine), load the form again and try again, up to three times.
  for (let attempt = 1; ; attempt += 1) {
    await page.getByLabel('Email or phone').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(password);
    try {
      await Promise.all([
        page.waitForResponse((r) => r.url().includes('/api/v1/auth/login'), { timeout: 8_000 }),
        page.getByRole('button', { name: 'Sign in' }).click(),
      ]);
      return;
    } catch (error) {
      if (attempt >= 3) throw error;
      await page.reload();
    }
  }
}

let counter = 0;

/**
 * Registers a brand-new advocate (the browser is signed in as them) who owns one case.
 * Tests that change data use this so they cannot disturb the seeded data other tests count.
 */
export async function newAdvocateWithCase(
  page: Page,
): Promise<{ caseTitle: string; caseId: string; advocateEmail: string }> {
  const unique = `${Date.now()}-${process.pid}-${counter++}`;
  const advocateEmail = `temp-${unique}@example.com`;
  const register = await page.request.post('/api/v1/auth/register', {
    data: {
      role: 'advocate',
      full_name: 'Adv. Temp Tester',
      email: advocateEmail,
      password: 'a-strong-password',
    },
  });
  expect(register.ok()).toBeTruthy();
  const caseTitle = `Edit v. Test ${unique}`;
  const created = await page.request.post('/api/v1/cases', {
    data: {
      title: caseTitle,
      cnr_number: `TMP-${unique}`,
      court: 'Saket District Court',
      parties: [
        { side: 'petitioner', name: 'Test Petitioner', is_client: true },
        { side: 'respondent', name: 'Test Respondent', is_client: false },
      ],
    },
  });
  expect(created.ok()).toBeTruthy();
  const caseId = (await created.json()).id as string;
  return { caseTitle, caseId, advocateEmail };
}

export const BASE_URL = 'http://localhost:5174';

export interface ClientScenario {
  advocate: Page;
  client: Page;
  caseId: string;
  caseTitle: string;
  clientEmail: string;
  close: () => Promise<void>;
}

/**
 * A throwaway advocate with one case and one invited client who has accepted, each in their own
 * browser context so the two sessions never mix. The advocate page is signed in as the advocate
 * and the client page as the client. Nothing is shared with the client yet.
 */
export async function createClientScenario(browser: Browser, advocate: Page): Promise<ClientScenario> {
  const { caseTitle, caseId } = await newAdvocateWithCase(advocate);

  const context = await browser.newContext({ baseURL: BASE_URL });
  const client = await context.newPage();
  await client.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  const clientEmail = `client-${Date.now()}-${process.pid}-${counter++}@example.com`;
  const registered = await client.request.post('/api/v1/auth/register', {
    data: { role: 'petitioner', full_name: 'Test Client', email: clientEmail, password: 'a-strong-password' },
  });
  expect(registered.ok()).toBeTruthy();

  const invited = await advocate.request.post(`/api/v1/cases/${caseId}/invitations`, {
    data: { contact: clientEmail },
  });
  expect(invited.ok()).toBeTruthy();
  const invitationId = (await invited.json()).id as string;
  const accepted = await client.request.post(`/api/v1/invitations/${invitationId}/accept`);
  expect(accepted.ok()).toBeTruthy();

  return { advocate, client, caseId, caseTitle, clientEmail, close: () => context.close() };
}

export interface ExtraClient {
  page: Page;
  email: string;
  close: () => Promise<void>;
}

/** Another invited client on the same case, in their own browser context. */
export async function addClient(browser: Browser, scenario: ClientScenario, name = 'Second Client'): Promise<ExtraClient> {
  const context = await browser.newContext({ baseURL: BASE_URL });
  const page = await context.newPage();
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  const email = `client2-${Date.now()}-${process.pid}-${counter++}@example.com`;
  const registered = await page.request.post('/api/v1/auth/register', {
    data: { role: 'petitioner', full_name: name, email, password: 'a-strong-password' },
  });
  expect(registered.ok()).toBeTruthy();
  const invited = await scenario.advocate.request.post(`/api/v1/cases/${scenario.caseId}/invitations`, {
    data: { contact: email },
  });
  const invitationId = (await invited.json()).id as string;
  expect((await page.request.post(`/api/v1/invitations/${invitationId}/accept`)).ok()).toBeTruthy();
  return { page, email, close: () => context.close() };
}

export interface Person {
  name: string;
  email: string;
  password: string;
  role: 'advocate' | 'petitioner';
  /** A page in the person's own browser, not yet signed in. */
  page: Page;
  close: () => Promise<void>;
}

/** Registers a brand-new advocate or client in a browser context of their own. */
export async function newPerson(
  browser: Browser,
  role: 'advocate' | 'petitioner',
  options: { name?: string; bar?: string } = {},
): Promise<Person> {
  const unique = `${Date.now()}-${process.pid}-${counter++}`;
  const name = options.name ?? `${role === 'advocate' ? 'Adv.' : ''} Person ${unique}`.trim();
  const email = `person-${unique}@example.com`;
  const context = await browser.newContext({ baseURL: BASE_URL });
  const page = await context.newPage();
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  const registered = await page.request.post('/api/v1/auth/register', {
    data: {
      role,
      full_name: name,
      email,
      password: 'a-strong-password',
      bar_registration_number: role === 'advocate' ? (options.bar ?? null) : null,
    },
  });
  expect(registered.ok()).toBeTruthy();
  await page.request.post('/api/v1/auth/logout'); // start signed out; tests sign in through the screens
  return { name, email, password: 'a-strong-password', role, page, close: () => context.close() };
}

/** An administrator signed in, in a browser context of their own. */
export async function newAdminPage(browser: Browser): Promise<{ page: Page; close: () => Promise<void> }> {
  const context = await browser.newContext({ baseURL: BASE_URL });
  const page = await context.newPage();
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  await signInAs(page, 'admin@example.com');
  await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
  return { page, close: () => context.close() };
}
