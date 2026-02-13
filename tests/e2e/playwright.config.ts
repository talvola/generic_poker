import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for poker platform E2E tests.
 *
 * Key considerations:
 * - Single worker to avoid table state conflicts between tests
 * - Serial execution (not parallel) for predictable game state
 * - Auto-start server before tests
 */
export default defineConfig({
  testDir: './specs',

  // Run tests serially - poker games have shared state
  fullyParallel: false,
  workers: 1,

  // Fail the build on CI if test.only is left in code
  forbidOnly: !!process.env.CI,

  // Retry failed tests on CI
  retries: process.env.CI ? 2 : 0,

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],

  // Shared settings for all projects
  use: {
    baseURL: 'http://localhost:5000',

    // Collect trace on first retry
    trace: 'on-first-retry',

    // Record video on first retry
    video: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Timeout for actions
    actionTimeout: 10000,

    // Navigation timeout
    navigationTimeout: 30000,
  },

  // Test timeout (poker games can take a while)
  timeout: 60000,

  // Expect timeout for assertions
  expect: {
    timeout: 10000,
  },

  // Projects - just Chromium for now
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Uncomment to test on other browsers
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Start the poker server before running tests
  webServer: {
    command: 'cd ../.. && source env/bin/activate && python app.py',
    url: 'http://localhost:5000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000, // 2 minutes to start server
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
