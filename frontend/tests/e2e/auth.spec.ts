import { expect, test } from './support/test';
import { signInAs } from './support/helpers';

const ADVOCATE = 'rohan.sharma@example.com';

test('welcome screen shows the brand panel and both roles', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'MrCourt' })).toBeVisible();
  await expect(page.getByText('Covers BNS, BNSS, BSA and the Constitution')).toBeVisible();
  await expect(page.getByText('Informational guidance only. Not legal advice.')).toBeVisible();
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
  await expect(page.getByRole('button', { name: "I'm a Petitioner" })).toBeVisible();
});

test('advocate signs in, sees a personalised dashboard, and signs out', async ({ page }) => {
  await signInAs(page, ADVOCATE);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Adv. Sharma');
  await expect(page.getByRole('link', { name: 'Drafts' })).toBeVisible();

  await page.getByRole('link', { name: 'Settings' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();

  // The session is gone: protected pages send the visitor back to the welcome screen.
  await page.goto('/dashboard');
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
});

test('wrong password shows a clear error and does not sign in', async ({ page }) => {
  await signInAs(page, ADVOCATE, 'not-the-password');
  await expect(page.getByRole('alert')).toContainText('Invalid email, phone or password');
  await expect(page).toHaveURL(/\/login/);
});

test('petitioner does not get the Drafts entry', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: "I'm a Petitioner" }).click();
  await page.getByLabel('Email or phone').fill('anita.sharma@example.com');
  await page.getByLabel('Password', { exact: true }).fill('password123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Drafts' })).toHaveCount(0);
});

test('the whole sign-in path works from the keyboard', async ({ page }) => {
  await page.goto('/');
  // The screen renders after the session check, so wait for it before using the keyboard.
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.getByLabel('Email or phone').focus();
  await page.keyboard.type(ADVOCATE);
  await page.keyboard.press('Tab');
  await page.keyboard.type('password123');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Adv. Sharma');
});

test('no horizontal scrolling on the welcome and sign-in screens', async ({ page }) => {
  for (const path of ['/', '/login']) {
    await page.goto(path);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  }
});

test('the password can be revealed and hidden again', async ({ page }) => {
  await page.goto('/login');
  const field = page.getByLabel('Password', { exact: true });
  await field.fill('my-secret-pass');
  await expect(field).toHaveAttribute('type', 'password');

  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(field).toHaveAttribute('type', 'text');
  await expect(field).toHaveValue('my-secret-pass');

  await page.getByRole('button', { name: 'Hide password' }).click();
  await expect(field).toHaveAttribute('type', 'password');
});

test('the password toggle works from the keyboard and keeps the field focusable', async ({ page }) => {
  await page.goto('/register');
  await page.getByLabel(/^Password/, { exact: false }).first().fill('abcdefghijk');
  const toggle = page.getByRole('button', { name: 'Show password' });
  await toggle.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Hide password' })).toBeVisible();
});

test.describe('the role chosen on the welcome screen must match the account', () => {
  async function tryBoth(page: import('@playwright/test').Page, button: string, email: string) {
    await page.goto('/');
    await page.getByRole('button', { name: button }).click();
    await page.getByLabel('Email or phone').fill(email);
    await page.getByLabel('Password', { exact: true }).fill('password123');
    await page.getByRole('button', { name: 'Sign in' }).click();
  }

  test("an advocate account cannot sign in through the Petitioner button", async ({ page }) => {
    await tryBoth(page, "I'm a Petitioner", ADVOCATE);
    await expect(page.getByRole('alert')).toContainText('registered as an Advocate, not a Petitioner');
    await expect(page.getByRole('alert')).toContainText('Please use the Advocate sign in');
    await expect(page).toHaveURL(/\/login\/petitioner/);
    // No session was left behind: the advocate's screens stay closed.
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
  });

  test("a petitioner account cannot sign in through the Advocate button", async ({ page }) => {
    await tryBoth(page, "I'm an Advocate", 'anita.sharma@example.com');
    await expect(page.getByRole('alert')).toContainText('registered as a Petitioner, not an Advocate');
    await expect(page.getByRole('alert')).toContainText('Please use the Petitioner sign in');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: "I'm a Petitioner" })).toBeVisible();
  });

  test("the matching choice signs in and shows only that person's screens", async ({ page }) => {
    await tryBoth(page, "I'm a Petitioner", 'anita.sharma@example.com');
    await expect(page.getByRole('link', { name: 'My cases' })).toBeVisible();
    await expect(page.locator('.clientcase')).toHaveCount(1);
    await expect(page.getByText('Active cases')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Drafts' })).toHaveCount(0);
  });
});

test.describe('separate sign-in and sign-up for advocates and petitioners', () => {
  test('the welcome buttons open different sign-in pages', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: "I'm an Advocate" }).click();
    await expect(page).toHaveURL(/\/login\/advocate$/);
    await expect(page.getByText('Advocate sign in', { exact: true })).toBeVisible();
    await expect(page.getByText('“The law is reason, free from passion.”')).toBeVisible();

    await page.getByRole('link', { name: 'Back' }).click();
    await page.getByRole('button', { name: "I'm a Petitioner" }).click();
    await expect(page).toHaveURL(/\/login\/petitioner$/);
    await expect(page.getByText('Petitioner sign in', { exact: true })).toBeVisible();
    await expect(page.getByText('Know where your case stands, and who is handling it.')).toBeVisible();
    await expect(page.getByText('Advocate sign in', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Aristotle')).toHaveCount(0);
  });

  test('each sign-in page links to the other', async ({ page }) => {
    await page.goto('/login/advocate');
    await page.getByRole('link', { name: 'Petitioner? Sign in here' }).click();
    await expect(page).toHaveURL(/\/login\/petitioner$/);
    await page.getByRole('link', { name: 'Advocate? Sign in here' }).click();
    await expect(page).toHaveURL(/\/login\/advocate$/);
  });

  test('switching pages does not carry typed details across', async ({ page }) => {
    await page.goto('/login/advocate');
    await page.getByLabel('Email or phone').fill('someone@example.com');
    await page.getByRole('link', { name: 'Petitioner? Sign in here' }).click();
    await expect(page.getByLabel('Email or phone')).toHaveValue('');
  });

  test('older links still work: /login and /register go to the advocate page, or the one asked for', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/\/login\/advocate$/);
    await page.goto('/login?role=petitioner');
    await expect(page).toHaveURL(/\/login\/petitioner$/);
    await page.goto('/register?role=petitioner');
    await expect(page.getByLabel('Petitioner')).toBeChecked();
  });

  test('one sign-up page lets the person pick the role, and the role decides the dashboard', async ({ page }) => {
    await page.goto('/register');
    await expect(page.getByRole('radio', { name: 'Advocate' })).toBeChecked();
    for (const label of ['Username', 'Email', 'Mobile number']) await expect(page.getByLabel(label, { exact: true })).toBeVisible();
    await page.getByRole('radio', { name: 'Petitioner' }).check();
    await expect(page.getByLabel('Bar Council registration number')).toHaveCount(0);
    await page.getByRole('radio', { name: 'Advocate' }).check();
    await expect(page.getByLabel('Bar Council registration number')).toBeVisible();
    await expect(page.getByRole('radio', { name: 'Administrator' })).toHaveCount(0);

    const stamp = `${Date.now()}${Math.floor(Math.random() * 1e6)}`;
    await page.getByLabel('Username', { exact: true }).fill(`Pick${stamp}`.slice(0, 30));
    await page.getByLabel('Full name').fill('Adv. Pick Role');
    await page.getByLabel('Email', { exact: true }).fill(`pick-${stamp}@example.com`);
    await page.getByLabel('Mobile number').fill(`+9193${stamp.slice(-8)}`);
    await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Create account' }).click();
    await page.getByRole('button', { name: 'Verify later' }).click();
    await expect(page.getByText('Active cases')).toBeVisible();
    await page.request.post('/api/v1/auth/logout');

    await page.goto('/login/advocate');
    await page.getByLabel('Email or phone').fill(`Pick${stamp}`.slice(0, 30).toUpperCase()); // username, any capitals
    await page.getByLabel('Password', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Active cases')).toBeVisible();
  });

  test('a username that is taken is refused with a clear message', async ({ page }) => {
    await page.goto('/register/petitioner');
    await page.getByLabel('Username', { exact: true }).fill('anita');
    await page.getByLabel('Full name').fill('Another Anita');
    await page.getByLabel('Email', { exact: true }).fill(`dup-${Date.now()}@example.com`);
    await page.getByLabel('Mobile number').fill(`+9192${Date.now().toString().slice(-8)}`);
    await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByRole('alert')).toContainText('username is taken');
  });

  test('an unknown page goes back to the welcome screen', async ({ page }) => {
    await page.goto('/login/administrator');
    await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
    await page.goto('/register/lawyer');
    await expect(page.getByRole('button', { name: "I'm a Petitioner" })).toBeVisible();
  });

  test('the sign-up page asks for username, email, password and role; only advocates give a Bar Council number', async ({ page }) => {
    await page.goto('/register/advocate');
    await expect(page.getByText('Advocate sign up', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Bar Council registration number')).toBeVisible();

    await page.goto('/register/petitioner');
    await expect(page.getByText('Petitioner sign up', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Bar Council registration number')).toHaveCount(0);
    await expect(page.getByText(/Your lawyer invites you to your case/)).toBeVisible();
  });

  test('a new petitioner signs up on their own page and lands on the client dashboard', async ({ page }) => {
    await page.goto('/register/petitioner');
    await page.getByLabel('Username', { exact: true }).fill(`u${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`);
    await page.getByLabel('Full name').fill('Nina Rao');
    await page.getByLabel(/^Email/).fill(`nina-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
    await page.getByLabel('Mobile number').fill(`+9197${Date.now().toString().slice(-8)}`);
    await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Create account' }).click();
    await page.getByRole('button', { name: 'Verify later' }).click();
    await expect(page.getByText('Your cases will appear here')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Drafts' })).toHaveCount(0);
  });

  test('a new advocate signs up on their own page and lands on the advocate dashboard', async ({ page }) => {
    await page.goto('/register/advocate');
    await page.getByLabel('Username', { exact: true }).fill(`u${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`);
    await page.getByLabel('Full name').fill('Adv. New Person');
    await page.getByLabel(/^Email/).fill(`newadv-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
    await page.getByLabel('Mobile number').fill(`+9196${Date.now().toString().slice(-8)}`);
    await page.getByLabel('Password (at least 10 characters)', { exact: true }).fill('a-strong-password');
    await page.getByRole('button', { name: 'Create account' }).click();
    await page.getByRole('button', { name: 'Verify later' }).click();
    await expect(page.getByText('Active cases')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Drafts' })).toBeVisible();
  });
});

test('the welcome screen links to the registration page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Create an account' }).click();
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
});
