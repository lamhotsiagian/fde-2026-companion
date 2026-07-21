import { defineConfig, devices } from '@playwright/test';

/** Playwright config for the guardrails UI screenshot suite. */
export default defineConfig({
  testDir: './tests-guardrails',
  timeout: 60_000,
  fullyParallel: false,          // one turn at a time; the local GPU is shared
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'test-results/report', open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    viewport: { width: 1280, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
