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
    // The seeded people have already agreed to voice control (feature 011), so the many tests that use their
    // accounts at the same time never race to save that agreement. Tests of the first-use notice use fresh accounts.
    for (const email of ['rohan.sharma@example.com', 'anita.sharma@example.com', 'admin@example.com']) {
      const context = await browser.newContext({ baseURL: 'http://localhost:8001' });
      const login = await context.request.post('/api/v1/auth/login', { data: { identifier: email, password: 'password123' } });
      if (login.ok()) await context.request.patch('/api/v1/me/settings', { data: { voice_consent: true } });
      await context.close();
    }
  } finally {
    await browser.close();
  }
}
