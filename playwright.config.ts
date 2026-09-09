import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/https.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5176',
    actionTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'python3 e2e/serve_backend.py',
      url: 'http://127.0.0.1:8010/api/b2c/csrf',
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: 'npm --prefix frontend run dev -- --host 127.0.0.1 --port 5176 --strictPort',
      env: { B2C_API_TARGET: 'http://127.0.0.1:8010' },
      url: 'http://127.0.0.1:5176',
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
