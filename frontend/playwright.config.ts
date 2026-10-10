import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  globalSetup: './tests/e2e/support/warm-up.ts',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  // Browsers, the dev server and the API share one machine; too many at once makes sign-in slow.
  workers: process.env.CI ? 2 : 4,
  // One retry everywhere: a sign-in request occasionally stalls when several browsers share the machine.
  // A retried test is reported as "flaky", so it stays visible rather than hidden.
  retries: process.env.CI ? 2 : 1,
  use: {
    baseURL: 'http://localhost:5174',
    trace: 'retain-on-failure',
    // A fake microphone, so recording can be tested without hardware or a permission prompt.
    permissions: ['microphone'],
    launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { ...devices['Pixel 5'], viewport: { width: 360, height: 740 } } },
  ],
  // End-to-end runs use their own API (fresh seeded database) and frontend, on separate ports,
  // so they never touch development data and every run starts from the same state.
  webServer: [
    {
      command: 'node tests/e2e/support/start-api.mjs',
      url: 'http://localhost:8001/api/v1/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      env: { PORT: '5174', API_URL: 'http://localhost:8001', VITE_UPDATES_POLL_MS: '3000' },
      url: 'http://localhost:5174',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
