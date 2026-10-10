import { test as base } from '@playwright/test';

export { expect } from '@playwright/test';

/**
 * Same as Playwright's `test`, but never waits on web fonts from the internet, so runs are fast and
 * do not depend on network access. Layout is verified with fallback fonts.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
    await use(page);
  },
});
