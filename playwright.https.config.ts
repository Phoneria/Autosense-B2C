import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  testMatch: 'https.spec.ts',
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-https-report', open: 'never' }]],
  outputDir: 'test-results-https',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'https://localhost:8443',
    // Only this explicitly local smoke stack uses a locally generated certificate.
    ignoreHTTPSErrors: true,
    actionTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
