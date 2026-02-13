/**
 * E2E regression tests for a complete Texas Hold'em hand lifecycle.
 *
 * Plays through all streets (preflop → flop → turn → river → showdown)
 * verifying UI rendering at each phase. This is the primary regression
 * test for the table.js refactoring in Phase 2.
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
  getCommunityCardCount,
  callCleanupApi,
  cleanupTestTables,
  BASE_URL
} from '../helpers';

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Determine which page is the current actor (has enabled action buttons).
 * Returns [actorPage, waitingPage, actorName].
 */
async function getActorAndWaiter(
  alicePage: Page,
  bobPage: Page
): Promise<[Page, Page, string]> {
  // Poll both pages - one should have action buttons
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
 * Play a complete betting round where both players check/call.
 * Returns the two pages in order [actor, waiter] for the NEXT round.
 */
async function playCheckCallRound(
  alicePage: Page,
  bobPage: Page,
  isPreflop: boolean = false
): Promise<void> {
  const [actor, waiter] = await getActorAndWaiter(alicePage, bobPage);

  if (isPreflop) {
    // Preflop: SB acts first, needs to call; BB then checks
    await performAction(actor, 'call');
    // Wait for BB to get action
    await expect(async () => {
      expect(await isMyTurn(waiter)).toBe(true);
    }).toPass({ timeout: 10000 });
    await performAction(waiter, 'check');
  } else {
    // Post-flop: first actor checks, second checks
    await performAction(actor, 'check');
    await expect(async () => {
      expect(await isMyTurn(waiter)).toBe(true);
    }).toPass({ timeout: 10000 });
    await performAction(waiter, 'check');
  }
}

// ============================================================================
// TESTS
// ============================================================================

test.describe('Full Hand Lifecycle', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('complete hand plays through all streets to showdown', async ({ alicePage, bobPage }) => {
    // Create and join table
    const tableName = await createTable(alicePage, { name: `Test Full Hand ${Date.now()}` });
    await joinTableByName(bobPage, tableName);

    // Wait for both players visible
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
    await expect(bobPage.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });

    // Ready up
    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    // === PREFLOP ===
    // Verify: each player sees 2 hole cards, pot shows blinds
    const aliceCardCount = await alicePage.locator('.player-cards .card').count();
    expect(aliceCardCount).toBeGreaterThanOrEqual(2);

    const initialPot = await getPotAmount(alicePage);
    expect(initialPot).toBe(3); // $1 SB + $2 BB

    // No community cards yet
    let communityCount = await getCommunityCardCount(alicePage);
    expect(communityCount).toBe(0);

    // Play preflop: SB calls, BB checks
    await playCheckCallRound(alicePage, bobPage, true);

    // === FLOP ===
    // Wait for 3 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    // Both players see the same 3 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(bobPage);
      expect(count).toBe(3);
    }).toPass({ timeout: 5000 });

    // Community cards should have rank and suit
    const flopCards = alicePage.locator('.card-slot.has-card .card');
    expect(await flopCards.count()).toBe(3);
    // Each card should have a rank element
    for (let i = 0; i < 3; i++) {
      await expect(flopCards.nth(i).locator('.card-rank')).toBeVisible();
      await expect(flopCards.nth(i).locator('.card-suit')).toBeVisible();
    }

    // Pot should be $4 after preflop (SB called to $2 + BB $2)
    await expect(async () => {
      const pot = await getPotAmount(alicePage);
      expect(pot).toBe(4);
    }).toPass({ timeout: 5000 });

    // Play flop: both check
    await playCheckCallRound(alicePage, bobPage);

    // === TURN ===
    // Wait for 4 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(4);
    }).toPass({ timeout: 10000 });

    // Play turn: both check
    await playCheckCallRound(alicePage, bobPage);

    // === RIVER ===
    // Wait for 5 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(5);
    }).toPass({ timeout: 10000 });

    // All 5 community card slots should have cards with rank/suit
    const allCommunityCards = alicePage.locator('.card-slot.has-card .card');
    expect(await allCommunityCards.count()).toBe(5);

    // Play river: both check
    await playCheckCallRound(alicePage, bobPage);

    // === SHOWDOWN ===
    // Wait for showdown results to appear
    await expect(async () => {
      const showdownContainer = alicePage.locator('#showdown-results-container');
      const isVisible = await showdownContainer.isVisible();
      expect(isVisible).toBe(true);
    }).toPass({ timeout: 15000 });

    // Showdown should show on bob's page too
    await expect(async () => {
      const showdownContainer = bobPage.locator('#showdown-results-container');
      const isVisible = await showdownContainer.isVisible();
      expect(isVisible).toBe(true);
    }).toPass({ timeout: 5000 });

    // Chat should have showdown messages
    const chatMessages = alicePage.locator('#chat-messages .chat-message');
    const messageCount = await chatMessages.count();
    expect(messageCount).toBeGreaterThan(0);

    // Look for "SHOW DOWN" in chat
    await expect(alicePage.locator('#chat-messages:has-text("SHOW DOWN")')).toBeVisible({ timeout: 5000 });

    // Look for winner announcement (contains "wins with" or "collected")
    const chatText = await alicePage.locator('#chat-messages').textContent();
    expect(chatText).toMatch(/wins with|collected|split/);
  });

  test('community cards render with correct structure', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Cards ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Play through preflop
    await playCheckCallRound(alicePage, bobPage, true);

    // Wait for flop
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    // Verify card structure: each card has data-rank and data-suit attributes
    const communityCards = alicePage.locator('.card-slot.has-card .card');
    for (let i = 0; i < 3; i++) {
      const card = communityCards.nth(i);
      const rank = await card.getAttribute('data-rank');
      const suit = await card.getAttribute('data-suit');
      expect(rank).toBeTruthy();
      expect(suit).toMatch(/^[hdcs]$/);
    }

    // Cards should be colored: red (h, d) or black (c, s)
    const firstCard = communityCards.first();
    const classList = await firstCard.getAttribute('class');
    expect(classList).toMatch(/red|black/);
  });

  test('pot updates correctly through streets', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Pot ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Preflop pot = $3 (blinds)
    expect(await getPotAmount(alicePage)).toBe(3);

    // SB calls → pot = $4
    await playCheckCallRound(alicePage, bobPage, true);
    await expect(async () => {
      expect(await getPotAmount(alicePage)).toBe(4);
    }).toPass({ timeout: 5000 });

    // Wait for flop
    await expect(async () => {
      expect(await getCommunityCardCount(alicePage)).toBe(3);
    }).toPass({ timeout: 10000 });

    // Check-check flop → pot still $4
    await playCheckCallRound(alicePage, bobPage);
    await expect(async () => {
      expect(await getPotAmount(alicePage)).toBe(4);
    }).toPass({ timeout: 5000 });

    // Wait for turn
    await expect(async () => {
      expect(await getCommunityCardCount(alicePage)).toBe(4);
    }).toPass({ timeout: 10000 });

    // Check-check turn → pot still $4
    await playCheckCallRound(alicePage, bobPage);
    await expect(async () => {
      expect(await getPotAmount(alicePage)).toBe(4);
    }).toPass({ timeout: 5000 });
  });
});
