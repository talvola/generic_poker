/**
 * E2E regression tests for specific UI element rendering.
 *
 * Verifies:
 * - Card backs shown for opponent's hole cards
 * - Position indicators (D, SB, BB) rendered correctly
 * - Player chip stacks displayed
 * - Bet controls (slider, quick-bet buttons) appear for bet/raise
 * - Action log messages in chat panel
 * - Waiting message when not your turn
 */
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
  getPotAmount,
  callCleanupApi,
  cleanupTestTables,
  BASE_URL
} from '../helpers';

// ============================================================================
// HELPERS
// ============================================================================

async function getActorAndWaiter(
  alicePage: Page,
  bobPage: Page
): Promise<[Page, Page, string]> {
  for (let i = 0; i < 20; i++) {
    const aliceActs = await isMyTurn(alicePage);
    if (aliceActs) return [alicePage, bobPage, 'alice'];
    const bobActs = await isMyTurn(bobPage);
    if (bobActs) return [bobPage, alicePage, 'bob'];
    await alicePage.waitForTimeout(500);
  }
  throw new Error('Neither player has action buttons after 10 seconds');
}

/**
 * Setup a standard 2-player game and return pages ready to play.
 */
async function setupGame(alicePage: Page, bobPage: Page): Promise<string> {
  const tableName = await createTable(alicePage, { name: `Test UI ${Date.now()}` });
  await joinTableByName(bobPage, tableName);
  await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
  await expect(bobPage.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });
  await clickReady(alicePage);
  await clickReady(bobPage);
  await waitForGameStart(alicePage);
  await waitForGameStart(bobPage);
  return tableName;
}

// ============================================================================
// TESTS
// ============================================================================

test.describe('Card Rendering', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('own hole cards are face-up with rank and suit', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Find current player's cards - they should have rank and suit elements
    // Each player sees their own cards face-up
    for (const page of [alicePage, bobPage]) {
      // Cards in the player's own seat should have .card-rank and .card-suit
      const faceUpCards = page.locator('.player-cards .card:not(.card-back)');
      const count = await faceUpCards.count();
      expect(count).toBeGreaterThanOrEqual(2);

      // Verify at least 2 cards have rank/suit
      for (let i = 0; i < 2; i++) {
        const card = faceUpCards.nth(i);
        await expect(card.locator('.card-rank')).toBeVisible();
        await expect(card.locator('.card-suit')).toBeVisible();
      }
    }
  });

  test('opponent hole cards show as card backs', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Each player should see card backs for the opponent
    for (const page of [alicePage, bobPage]) {
      const cardBacks = page.locator('.player-cards .card-back');
      const backCount = await cardBacks.count();
      expect(backCount).toBeGreaterThanOrEqual(2);

      // Card backs should show the back symbol
      const firstBack = await cardBacks.first().textContent();
      expect(firstBack?.trim()).toContain('🂠');
    }
  });
});

test.describe('Position Indicators', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('dealer, SB, and BB indicators are shown', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // In heads-up, dealer=SB and the other player is BB
    // So we should see D, SB on one player and BB on the other

    // Check for position indicator elements
    const allIndicators = alicePage.locator('.position-indicator');
    const indicatorCount = await allIndicators.count();
    expect(indicatorCount).toBeGreaterThanOrEqual(2); // At least D/SB and BB

    // Should have a dealer indicator
    await expect(alicePage.locator('.position-indicator.dealer')).toBeVisible();

    // Should have a big blind indicator
    await expect(alicePage.locator('.position-indicator.big-blind')).toBeVisible();
  });
});

test.describe('Action Panel', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('current player sees action buttons, other sees waiting message', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    const [actor, waiter] = await getActorAndWaiter(alicePage, bobPage);

    // Actor should have visible, enabled action buttons
    const actionButtons = actor.locator('.action-btn:not([disabled])');
    const btnCount = await actionButtons.count();
    expect(btnCount).toBeGreaterThanOrEqual(2); // At least fold + call/check

    // Waiter should see "Waiting for your turn..." message
    await expect(waiter.locator('.waiting-message')).toBeVisible();
  });

  test('preflop SB sees fold, call, and raise buttons', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // SB acts first preflop in heads-up
    const [sbPage] = await getActorAndWaiter(alicePage, bobPage);

    // Should see Fold button
    await expect(sbPage.locator('.action-btn.fold')).toBeVisible();

    // Should see Call button (with amount)
    await expect(sbPage.locator('.action-btn.call')).toBeVisible();

    // Should see Raise button
    await expect(sbPage.locator('.action-btn.raise')).toBeVisible();
  });

  test('bet controls elements exist in DOM when raise available', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    const [actor] = await getActorAndWaiter(alicePage, bobPage);

    // Raise button should be visible for preflop SB
    await expect(actor.locator('.action-btn.raise')).toBeVisible();

    // Bet controls elements should be in the DOM (may not be scrolled into view)
    await expect(actor.locator('#bet-controls')).toBeAttached();
    await expect(actor.locator('#bet-slider')).toBeAttached();
    await expect(actor.locator('#bet-amount')).toBeAttached();
    await expect(actor.locator('.quick-bet-btn[data-action="min"]')).toBeAttached();
    await expect(actor.locator('.quick-bet-btn[data-action="all-in"]')).toBeAttached();
  });
});

test.describe('Player Info Display', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('player names and chip stacks are displayed', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Both pages should show player names
    for (const page of [alicePage, bobPage]) {
      await expect(page.locator('.player-name:has-text("alice")')).toBeVisible();
      await expect(page.locator('.player-name:has-text("bob")')).toBeVisible();

      // Chip stacks should show dollar amounts
      const chipDisplays = page.locator('.player-chips');
      const chipCount = await chipDisplays.count();
      expect(chipCount).toBeGreaterThanOrEqual(2);

      for (let i = 0; i < chipCount; i++) {
        const text = await chipDisplays.nth(i).textContent();
        expect(text).toMatch(/\$\d+/); // Should contain $amount
      }
    }
  });

  test('folded indicator shows after fold', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Get SB to fold
    const [actor, waiter, actorName] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(actor, 'fold');

    // The folded player should show a FOLDED indicator on the waiter's screen
    await expect(async () => {
      const foldedIndicator = waiter.locator('.folded-indicator');
      const isVisible = await foldedIndicator.isVisible();
      expect(isVisible).toBe(true);
    }).toPass({ timeout: 10000 });
  });
});

test.describe('Chat Action Log', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('blind posts appear in action log', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Chat should show blind posting messages
    await expect(async () => {
      const chatText = await alicePage.locator('#chat-messages').textContent();
      // Should mention blinds or ante
      expect(chatText?.toLowerCase()).toMatch(/blind|ante|post/);
    }).toPass({ timeout: 10000 });
  });

  test('player actions appear in action log', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // SB calls
    const [actor, waiter] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(actor, 'call');

    // Chat should show the call action
    await expect(async () => {
      const chatText = await waiter.locator('#chat-messages').textContent();
      expect(chatText?.toLowerCase()).toMatch(/call/);
    }).toPass({ timeout: 10000 });
  });

  test('community card announcements appear in log', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Play through preflop
    const [actor, waiter] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(actor, 'call');
    await expect(async () => {
      expect(await isMyTurn(waiter)).toBe(true);
    }).toPass({ timeout: 10000 });
    await performAction(waiter, 'check');

    // Wait for flop
    await expect(async () => {
      const chatText = await alicePage.locator('#chat-messages').textContent();
      expect(chatText).toMatch(/FLOP/);
    }).toPass({ timeout: 15000 });
  });
});

test.describe('Table Layout', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('header shows table name and stakes', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Layout ${Date.now()}` });

    // Header should show table name
    await expect(alicePage.locator('.table-name')).toContainText('Test Layout');

    // Should show stakes (template renders "$1/2" with $ only on small blind)
    await expect(alicePage.locator('.stakes')).toContainText('1/2');

    // Should show betting structure
    await expect(alicePage.locator('.structure')).toBeVisible();
  });

  test('pot info area is visible during game', async ({ alicePage, bobPage }) => {
    await setupGame(alicePage, bobPage);

    // Pot label and amount should be visible
    await expect(alicePage.locator('.pot-label')).toBeVisible();
    await expect(alicePage.locator('.pot-amount')).toBeVisible();

    // Pot should show at least the blinds
    const potText = await alicePage.locator('.pot-amount').textContent();
    expect(potText).toMatch(/\$\d+/);
  });
});
