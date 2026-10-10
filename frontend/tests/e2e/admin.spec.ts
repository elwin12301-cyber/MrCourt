import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

const MENU = ['Overview', 'Advocates', 'Clients', 'Cases', 'Verifications', 'Ask MrCourt', 'Audit log', 'Settings'];

test.describe('administrator', () => {
  test.beforeEach(async ({ page }) => {
    await signInAs(page, 'admin@example.com');
    await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
  });

  test('has a menu of their own and none of the advocate or client screens', async ({ page }) => {
    const menu = page.getByRole('navigation', { name: 'Main' });
    for (const name of MENU) await expect(menu.getByRole('link', { name, exact: true })).toBeVisible();
    for (const name of ['Drafts', 'Updates', 'My cases', 'Dashboard']) {
      await expect(menu.getByRole('link', { name, exact: true })).toHaveCount(0);
    }
    await expect(menu.getByRole('link')).toHaveCount(MENU.length);
    await expect(page.locator('.user small')).toHaveText('Administrator');
  });

  test('the overview shows the numbers and links to the lists', async ({ page }) => {
    for (const label of ['Advocates', 'Clients', 'Open cases', 'Waiting for verification', 'Suspended accounts']) {
      await expect(page.locator('.statlink', { hasText: label })).toBeVisible();
    }
    await expect(page.locator('.statlink', { hasText: 'Advocates' }).locator('b')).toHaveText(/^\d+$/);
    await expect(page.getByRole('heading', { name: 'Latest activity' })).toBeVisible();

    await page.locator('.statlink', { hasText: 'Clients' }).click();
    await expect(page).toHaveURL(/\/admin\/clients$/);
  });

  test('advocate and client screens are closed to the administrator', async ({ page }) => {
    for (const path of ['/cases', '/drafts', '/updates']) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(page.getByRole('heading', { name: 'Administration', level: 1 })).toBeVisible();
    }
  });

  test('settings has no way to deactivate the administrator account', async ({ page }) => {
    await page.getByRole('link', { name: 'Settings', exact: true }).click();
    await page.getByRole('button', { name: 'Manage' }).click();
    await expect(page.getByRole('button', { name: 'Download my data' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Deactivate account' })).toHaveCount(0);
  });
});

test.describe('the three sign-ins stay separate', () => {
  test('the welcome screen offers the administrator sign-in as a small link', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Administrator sign in' }).click();
    await expect(page).toHaveURL(/\/login\/admin$/);
    await expect(page.getByText('Administrator sign in', { exact: true })).toBeVisible();
    await expect(page.getByText('Looking after the people and the cases on MrCourt.')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Create an account' })).toHaveCount(0); // no public sign-up
  });

  async function attempt(page: import('@playwright/test').Page, url: string, email: string) {
    await page.goto(url);
    await page.getByLabel('Email or phone').fill(email);
    await page.getByLabel('Password', { exact: true }).fill('password123');
    await page.getByRole('button', { name: 'Sign in' }).click();
  }

  test('an advocate cannot sign in on the administrator page', async ({ page }) => {
    await attempt(page, '/login/admin', 'rohan.sharma@example.com');
    await expect(page.getByRole('alert')).toContainText('registered as an Advocate, not an Administrator');
    await expect(page.getByRole('alert')).toContainText('Please use the Advocate sign in');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible(); // no session left
  });

  test('a client cannot sign in on the administrator page', async ({ page }) => {
    await attempt(page, '/login/admin', 'anita.sharma@example.com');
    await expect(page.getByRole('alert')).toContainText('registered as a Petitioner, not an Administrator');
  });

  test('the administrator cannot sign in on the advocate or petitioner pages', async ({ page }) => {
    await attempt(page, '/login/advocate', 'admin@example.com');
    await expect(page.getByRole('alert')).toContainText('registered as an Administrator, not an Advocate');
    await expect(page.getByRole('alert')).toContainText('Please use the Administrator sign in');
    await attempt(page, '/login/petitioner', 'admin@example.com');
    await expect(page.getByRole('alert')).toContainText('registered as an Administrator, not a Petitioner');
  });

  test('advocates and clients are told admin pages are not for them, and see none of the admin menu', async ({ page }) => {
    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    for (const path of ['/admin/advocates', '/admin/cases', '/admin/audit', '/admin/verifications']) {
      await page.goto(path);
      await expect(page.getByText('This page is for administrators only.')).toBeVisible();
    }
    for (const name of ['Advocates', 'Clients', 'Audit log', 'Verifications']) {
      await expect(page.getByRole('link', { name, exact: true })).toHaveCount(0);
    }
  });

  test('there is no public sign-up for administrators', async ({ page }) => {
    await page.goto('/register/admin');
    await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible(); // sent back to the welcome screen
  });
});
