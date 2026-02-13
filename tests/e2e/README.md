# E2E Testing Guide

This directory contains end-to-end tests for the poker platform UI using Playwright.

## Quick Start

```bash
# Prerequisites
cd tests/e2e
npm install

# Start the server (separate terminal)
cd /home/erik/generic_poker
source env/bin/activate
python tools/reset_db.py  # Fresh database
python app.py

# Run tests
npx playwright test
```

## Multi-Player Testing - CRITICAL ARCHITECTURE

### The Session Cookie Problem (400 "Not your turn to act" Error)

Testing multiplayer poker requires multiple simultaneous users. The most common error when setting this up incorrectly is:

**HTTP 400: "Not your turn to act"**

This error occurs when multiple browser tabs share the same session cookie. The server sees all requests as coming from the **same user**, regardless of which tab is making the request.

### The Solution: Separate Browser Contexts

Playwright's **Browser Contexts** provide isolated sessions. Each context has its own:
- Cookies
- localStorage
- Session state

```
Browser (Chromium)
├── Context: Alice (isolated session, logged in as alice)
│   └── Page: Table view
├── Context: Bob (isolated session, logged in as bob)
│   └── Page: Table view
└── Context: Spectator (isolated session)
    └── Page: Table view
```

### How Our Fixture Works

The `fixtures/multi-user.ts` file creates separate browser contexts for each test user:

```typescript
// Each user gets their own context with isolated cookies
aliceContext: async ({ browser }, use) => {
  const context = await browser.newContext();  // New context = isolated session
  const page = await context.newPage();
  // Login as alice...
  await use(context);
  await context.close();
},

bobContext: async ({ browser }, use) => {
  const context = await browser.newContext();  // Separate context = separate session
  const page = await context.newPage();
  // Login as bob...
  await use(context);
  await context.close();
},
```

### WRONG vs CORRECT Approach

```typescript
// WRONG - shares session cookie, causes 400 errors
const page1 = await context.newPage();  // Tab 1
const page2 = await context.newPage();  // Tab 2 - SAME cookies as Tab 1!
// Both pages share the same session - server sees only ONE user

// CORRECT - separate contexts, separate sessions
const context1 = await browser.newContext();  // Context 1
const context2 = await browser.newContext();  // Context 2 - different cookies!
const page1 = await context1.newPage();
const page2 = await context2.newPage();
// Each page has its own session - server sees TWO different users
```

## Project Structure

```
tests/e2e/
├── README.md                    # This file
├── playwright.config.ts         # Playwright configuration
├── package.json                 # Node dependencies
├── fixtures/
│   └── multi-user.ts           # Multi-user test fixtures (CRITICAL)
├── auth/
│   ├── alice.json              # Saved auth state for alice
│   └── bob.json                # Saved auth state for bob
├── helpers/
│   ├── index.ts                # Central exports
│   └── table-helpers.ts        # Reusable test functions
└── specs/
    └── preflop-betting.spec.ts # Preflop betting tests
```

## Reusable Helpers

All common test operations are in `helpers/table-helpers.ts`:

```typescript
import {
  test,
  expect,
  createTable,        // Create new table from lobby
  joinTableByName,    // Join existing table from lobby
  clickReady,         // Click ready button
  waitForGameStart,   // Wait for cards to be dealt
  isMyTurn,           // Check if action buttons are enabled
  performAction,      // Perform fold/call/check/raise/bet
  getPotAmount,       // Get current pot
  getCommunityCardCount,  // Count community cards
  cleanupTestTables,  // Database cleanup
  callCleanupApi      // Server-side cleanup
} from '../helpers';
```

## Writing New Tests

### Template for Multiplayer Tests

```typescript
import { Page } from '@playwright/test';
import {
  test,
  expect,
  createTable,
  joinTableByName,
  clickReady,
  waitForGameStart,
  isMyTurn,
  performAction,
  callCleanupApi,
  cleanupTestTables
} from '../helpers';

test.describe('My Test Suite', () => {

  // IMPORTANT: Clean up before each test
  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('my multiplayer test', async ({ alicePage, bobPage }) => {
    // alicePage and bobPage are in SEPARATE browser contexts
    // They have different session cookies and are seen as different users

    // 1. Create unique table (use timestamp to avoid conflicts)
    const tableName = await createTable(alicePage, {
      name: `Test ${Date.now()}`
    });

    // 2. Second player joins via lobby (NOT direct URL)
    await joinTableByName(bobPage, tableName);

    // 3. Both ready up
    await clickReady(alicePage);
    await clickReady(bobPage);

    // 4. Wait for game to start
    await waitForGameStart(alicePage);

    // 5. Perform actions based on whose turn it is
    if (await isMyTurn(alicePage)) {
      await performAction(alicePage, 'call');
    } else {
      await performAction(bobPage, 'call');
    }

    // 6. Assert expected state
    // ...
  });
});
```

## Lessons Learned

### 1. Session Cookie Isolation (CRITICAL - Root Cause of 400 Errors)

**Problem:** "Not your turn to act" 400 errors when testing with multiple users.

**Root Cause:** Multiple browser tabs in the SAME context share session cookies. The server sees all requests as from one user.

**Solution:** Use SEPARATE browser contexts via `browser.newContext()`. Our multi-user fixture handles this automatically - just use `alicePage` and `bobPage` from the fixture.

### 2. Table Access Control

**Problem:** Second player navigating directly to table URL gets redirected to lobby.

**Root Cause:** The table view requires a `table_access` database record. Simply knowing the URL is not enough.

**Solution:** Both players must go through the proper join flow via `joinTableByName()`:
1. Navigate to lobby
2. Find table card
3. Click Join button
4. Complete seat selection modal
5. This creates the `table_access` record

```typescript
// WRONG - direct navigation fails
await page.goto(`http://localhost:5000/table/${tableId}`);

// CORRECT - go through lobby join flow
await joinTableByName(page, tableName);
```

### 3. In-Memory Game Sessions

**Problem:** Tests pass individually but fail when run together.

**Root Cause:** The `GameOrchestrator` keeps game sessions in memory. Database cleanup doesn't reset game state.

**Solution:**
1. Create unique tables per test (use `Date.now()` in name)
2. Call cleanup API in `beforeEach`
3. The test cleanup API clears both database AND in-memory sessions

```typescript
test.beforeEach(async ({ alicePage }) => {
  await callCleanupApi(alicePage);  // Clears sessions + test tables
  await cleanupTestTables();         // Database cleanup
});

// Create unique table for this test
const tableName = await createTable(alicePage, {
  name: `Test Hold'em ${Date.now()}`
});
```

### 4. SQL Escaping with Apostrophes

**Problem:** SQL queries fail for tables named like "Texas Hold'em".

**Solution:** Use LIKE patterns or properly escape:

```sql
-- WRONG
WHERE name='Texas Hold'em - Micro Stakes'

-- CORRECT
WHERE name LIKE '%Texas Hold%Micro Stakes%'
```

### 5. Modal Visibility

**Problem:** Create Table modal not appearing after button click.

**Root Cause:** Modal uses CSS `display: none` by default, needs JavaScript to add `show` class.

**Solution:** Wait for modal with `show` class:

```typescript
const modal = page.locator('#create-table-modal.show');
await expect(modal).toBeVisible({ timeout: 5000 });
```

### 6. WebSocket Timing

**Problem:** Tests fail because UI hasn't updated after action.

**Root Cause:** WebSocket updates are asynchronous. DOM may not reflect game state immediately.

**Solution:** Use Playwright's `expect().toPass()` for polling assertions:

```typescript
await expect(async () => {
  const count = await getCommunityCardCount(page);
  expect(count).toBe(3);
}).toPass({ timeout: 5000 });
```

### 7. Form Navigation

**Problem:** Table creation form submits but page doesn't navigate.

**Root Cause:** JavaScript redirect may fail silently or not trigger.

**Solution:** The `createTable` helper handles this with fallback navigation:
1. Click Create button
2. Wait for navigation OR
3. If still on lobby, find the created table and click Join

## Test API Endpoints

For E2E testing, the server provides test-only endpoints at `/api/test/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/test/cleanup` | POST | Delete all test tables (name starts with "Test ") and clear their game sessions |
| `/api/test/reset-table/<id>` | POST | Reset a specific table's game session |
| `/api/test/status` | GET | Get test environment status |

These endpoints are defined in `src/online_poker/routes/test_routes.py`.

**Note:** In production, these endpoints should be disabled or protected.

## Running Tests

```bash
# Run all e2e tests
npx playwright test

# Run specific test file
npx playwright test preflop-betting

# Run with UI mode (great for debugging)
npx playwright test --ui

# Run headed (see the browser)
npx playwright test --headed

# Debug mode (step through)
npx playwright test --debug
```

## Troubleshooting

### Tests fail with "Not your turn to act" (400 error)
- **This is the session cookie issue!**
- Ensure tests use `alicePage` and `bobPage` from the multi-user fixture
- Never create two pages from the same context for different users
- Verify the fixture is creating separate contexts (check `fixtures/multi-user.ts`)

### Tests fail with redirect to lobby
- User needs `table_access` record
- Use `joinTableByName()` instead of direct URL navigation

### Tests fail intermittently
- Add waits for WebSocket updates
- Use `expect().toPass()` for async assertions
- Check for race conditions in game state

### Ready button not visible
- Game may already be in progress from previous test
- Ensure cleanup runs before each test
- Create unique tables per test

### Database errors
- Run `python tools/reset_db.py` for fresh database
- Check `instance/poker_platform.db` exists
- Verify test user credentials (alice/password, bob/password)

### Modal not appearing
- Check if JavaScript needs to add `show` class
- Wait for `.modal.show` selector, not just `.modal`

## Multi-User Fixture Details

The `fixtures/multi-user.ts` file provides pre-configured browser contexts for alice and bob:

```typescript
import { test as base, Page, BrowserContext, expect } from '@playwright/test';

export const test = base.extend<{
  aliceContext: BrowserContext;  // Separate context for alice
  bobContext: BrowserContext;    // Separate context for bob
  alicePage: Page;
  bobPage: Page;
}>({
  aliceContext: async ({ browser }, use) => {
    // Creates NEW context - isolated cookies/session
    const context = await browser.newContext();
    const page = await context.newPage();
    // Login as alice...
    await use(context);
    await context.close();
  },

  bobContext: async ({ browser }, use) => {
    // Creates ANOTHER NEW context - different cookies/session
    const context = await browser.newContext();
    const page = await context.newPage();
    // Login as bob...
    await use(context);
    await context.close();
  },

  alicePage: async ({ aliceContext }, use) => {
    const page = await aliceContext.newPage();
    await use(page);
  },

  bobPage: async ({ bobContext }, use) => {
    const page = await bobContext.newPage();
    await use(page);
  }
});

export { expect } from '@playwright/test';
```

## WebSocket Considerations

The poker platform uses WebSocket for real-time updates. Playwright handles this automatically, but note:

1. **Wait for WebSocket events** - Use `page.waitForEvent('websocket')` if needed
2. **State synchronization** - After actions, wait for UI updates rather than using fixed delays
3. **Use `expect` with auto-retry** - Playwright's expect automatically retries assertions

```typescript
// Good: Uses auto-retry
await expect(page.locator('.community-cards .card')).toHaveCount(3);

// Bad: Fixed delay
await page.waitForTimeout(1000);
const count = await page.locator('.community-cards .card').count();
expect(count).toBe(3);
```

## Debugging Tips

1. **Use Playwright UI mode**: `npx playwright test --ui`
2. **Enable tracing**: Traces show timeline of actions, network, console
3. **Screenshots on failure**: Configured in playwright.config.ts
4. **Use `page.pause()`**: Stops execution for debugging in headed mode

```typescript
test('debug example', async ({ alicePage }) => {
  await alicePage.goto('http://localhost:5000/');
  await alicePage.pause(); // Opens Playwright Inspector
});
```

## Test Credentials

| Username | Password |
|----------|----------|
| alice    | password |
| bob      | password |
| charlie  | password |

Make sure these users exist in the database (run `python tools/reset_db.py`).
