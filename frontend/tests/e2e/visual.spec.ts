import { expect, test } from './support/test';
import { PROTOTYPE_URL, setTheme, signInAs, type ThemeName } from './support/helpers';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';
import type { Page } from '@playwright/test';

/**
 * Compares screens with the untouched prototype (design/MrCourt Web Prototype.html), pixel by
 * pixel, with web fonts blocked on both sides so only layout and colour are being compared.
 * Screens whose content is live data (dashboard, cases, ...) are compared by their shared chrome.
 */
async function openPrototype(page: Page): Promise<Page> {
  const proto = await page.context().newPage();
  await proto.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
  await proto.goto(PROTOTYPE_URL);
  return proto;
}

function diffRatio(a: Buffer, b: Buffer): number {
  const imgA = PNG.sync.read(a);
  const imgB = PNG.sync.read(b);
  if (imgA.width !== imgB.width || imgA.height !== imgB.height) return 1;
  const changed = pixelmatch(imgA.data, imgB.data, null, imgA.width, imgA.height, { threshold: 0.1 });
  return changed / (imgA.width * imgA.height);
}

const THEMES: ThemeName[] = ['light', 'dark'];

for (const theme of THEMES) {
  test(`welcome screen matches the prototype (${theme})`, async ({ page }) => {
    const proto = await openPrototype(page);
    await setTheme(proto, theme);
    await expect(proto.locator('#welcome')).toBeVisible();
    const expected = await proto.screenshot();

    await page.goto('/');
    await setTheme(page, theme);
    await expect(page.getByRole('button', { name: "I'm an Advocate" })).toBeVisible();
    // The voice control launcher (feature 011) is a deliberate addition to the prototype: compare without it.
    await page.addStyleTag({ content: '.vc-dock{display:none!important}' });
    const actual = await page.screenshot();

    const ratio = diffRatio(expected, actual);
    console.log(`welcome ${theme}: ${(ratio * 100).toFixed(3)}% of pixels differ`);
    expect(ratio).toBeLessThan(0.005);
  });

  test(`sign-in brand panel matches the prototype (${theme})`, async ({ page }) => {
    // Only the brand half is compared. In the prototype the sign-in <form> is not covered by the
    // `.panel>div` rule, so its fields and buttons are cramped and unspaced; we apply that rule to
    // the form too (see the "Additions beyond the prototype" note in app.css). That is an
    // intentional difference, so the form half is deliberately not compared.
    const proto = await openPrototype(page);
    await setTheme(proto, theme);
    await proto.locator('#welcome [data-go="login"]').first().click();
    await expect(proto.locator('#login')).toBeVisible();
    const expected = await proto.locator('#login .brand').screenshot();

    await page.goto('/login');
    await setTheme(page, theme);
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
    const actual = await page.locator('#login .brand').screenshot();

    const ratio = diffRatio(expected, actual);
    console.log(`sign-in brand ${theme}: ${(ratio * 100).toFixed(3)}% of pixels differ`);
    expect(ratio).toBeLessThan(0.005);
  });

  test(`app navigation chrome matches the prototype (${theme})`, async ({ page }) => {
    const proto = await openPrototype(page);
    await setTheme(proto, theme);
    await proto.locator('#welcome [data-go="login"]').first().click();
    await proto.locator('#login [data-go="dashboard"]').click();
    await expect(proto.locator('#app')).toBeVisible();
    // The menu items are redesigned on purpose (two-colour menus), so only the logo area is compared.
    const expected = await proto.locator('.side .logo').screenshot();

    await signInAs(page, 'rohan.sharma@example.com');
    await expect(page.locator('.side')).toBeVisible();
    await setTheme(page, theme);
    const actual = await page.locator('.side .logo').screenshot();

    const ratio = diffRatio(expected, actual);
    console.log(`navigation ${theme}: ${(ratio * 100).toFixed(3)}% of pixels differ`);
    expect(ratio).toBeLessThan(0.005);
  });
}
