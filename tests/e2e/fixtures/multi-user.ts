/**
 * Multi-user test fixtures for poker platform E2E testing.
 *
 * These fixtures provide isolated browser contexts for multiple players,
 * each with their own session/cookies.
 */
import { test as base, Page, BrowserContext, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const AUTH_DIR = path.join(__dirname, '..', 'auth');

// Fixture types
type MultiUserFixtures = {
  aliceContext: BrowserContext;
  bobContext: BrowserContext;
  charlieContext: BrowserContext;
  alicePage: Page;
  bobPage: Page;
  charliePage: Page;
};

/**
 * Login a user and save their auth state to a file.
 * Creates an isolated browser context for this user.
 */
async function loginAndSaveState(
  browser: any,
  username: string,
  password: string,
  authFile: string
): Promise<BrowserContext> {
  // Create a completely fresh context for this user
  const context = await browser.newContext();
  const page = await context.newPage();

  // Navigate to login page
  await page.goto('http://localhost:5000/auth/login');

  // Wait for login form to be ready
  await expect(page.locator('input[name="username"]')).toBeVisible({ timeout: 5000 });

  // Fill in credentials
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // Wait for redirect to lobby
  await page.waitForURL('http://localhost:5000/', { timeout: 10000 });

  // Verify the EXACT username appears in the header (confirms login succeeded)
  // Using exact match to ensure we're logged in as the correct user
  const usernameDisplay = page.locator('.username');
  await expect(usernameDisplay).toBeVisible({ timeout: 5000 });
  const displayedUsername = await usernameDisplay.textContent();
  if (displayedUsername?.trim() !== username) {
    throw new Error(`Expected user ${username} but got ${displayedUsername}`);
  }

  // Save auth state for future use
  await context.storageState({ path: authFile });

  // Close the page but keep context
  await page.close();

  return context;
}

/**
 * Get or create an authenticated context for a user.
 * Always performs fresh login for test reliability.
 */
async function getAuthenticatedContext(
  browser: any,
  username: string,
  password: string
): Promise<BrowserContext> {
  const authFile = path.join(AUTH_DIR, `${username}.json`);

  // Ensure auth directory exists
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  // Always login fresh for test reliability
  return await loginAndSaveState(browser, username, password, authFile);
}

/**
 * Extended test with multi-user fixtures.
 */
export const test = base.extend<MultiUserFixtures>({
  // Alice context - first player
  aliceContext: async ({ browser }, use) => {
    const context = await getAuthenticatedContext(browser, 'alice', 'password');
    await use(context);
    await context.close();
  },

  // Bob context - second player
  bobContext: async ({ browser }, use) => {
    const context = await getAuthenticatedContext(browser, 'bob', 'password');
    await use(context);
    await context.close();
  },

  // Charlie context - third player (for 3+ player games)
  charlieContext: async ({ browser }, use) => {
    const context = await getAuthenticatedContext(browser, 'charlie', 'password');
    await use(context);
    await context.close();
  },

  // Pages for each player
  alicePage: async ({ aliceContext }, use) => {
    const page = await aliceContext.newPage();
    await use(page);
  },

  bobPage: async ({ bobContext }, use) => {
    const page = await bobContext.newPage();
    await use(page);
  },

  charliePage: async ({ charlieContext }, use) => {
    const page = await charlieContext.newPage();
    await use(page);
  },
});

export { expect };
