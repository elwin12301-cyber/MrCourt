import { chromium } from '@playwright/test';

/**
 * The development server compiles each module the first time a page asks for it. With several
 * browsers starting at once, the first test in each file can run out of time waiting for that.
 * Loading the app once, before any test, pays that cost up front.
 */
export default async function warmUp() {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
    for (const path of ['/', '/login/advocate', '/login/admin']) {
      await page.goto(`http://localhost:5174${path}`, { waitUntil: 'networkidle' });
    }
  } finally {
    await browser.close();
  }
}
