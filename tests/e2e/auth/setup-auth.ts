/**
 * Setup script to pre-generate authentication states for test users.
 *
 * Run this before tests to create auth/*.json files that can be reused,
 * making tests faster by skipping login each time.
 *
 * Usage: npx ts-node auth/setup-auth.ts
 */
import { chromium } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = 'http://localhost:5000';

const TEST_USERS = [
  { username: 'alice', password: 'password' },
  { username: 'bob', password: 'password' },
  { username: 'charlie', password: 'password' },
  { username: 'diana', password: 'password' },
  { username: 'testuser', password: 'password' },
];

async function setupAuthStates() {
  console.log('Setting up authentication states for test users...\n');

  const browser = await chromium.launch({ headless: true });

  for (const user of TEST_USERS) {
    console.log(`Logging in as ${user.username}...`);

    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      // Navigate to login page
      await page.goto(`${BASE_URL}/auth/login`);

      // Fill in credentials
      await page.fill('input[name="username"]', user.username);
      await page.fill('input[name="password"]', user.password);

      // Submit login
      await page.click('button[type="submit"]');

      // Wait for redirect to lobby
      await page.waitForURL(`${BASE_URL}/`, { timeout: 10000 });

      // Verify we're logged in
      const usernameDisplay = await page.textContent('.username, [class*="user"]');
      if (!usernameDisplay?.includes(user.username)) {
        console.error(`  Failed to login as ${user.username}`);
        await context.close();
        continue;
      }

      // Save auth state
      const authFile = path.join(__dirname, `${user.username}.json`);
      await context.storageState({ path: authFile });

      console.log(`  Saved auth state to ${authFile}`);

    } catch (error) {
      console.error(`  Error logging in as ${user.username}:`, error);
    }

    await context.close();
  }

  await browser.close();

  console.log('\nAuth setup complete!');
  console.log('You can now run tests with: npm test');
}

// Run the setup
setupAuthStates().catch(console.error);
