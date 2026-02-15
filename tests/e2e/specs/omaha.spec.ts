/**
 * E2E tests for Omaha poker variant.
 *
 * Verifies that Omaha (4 hole cards) renders correctly in the browser,
 * including the many-cards CSS class for layout and full hand playthrough.
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

async function playCheckCallRound(
  alicePage: Page,
  bobPage: Page,
  isPreflop: boolean = false
): Promise<void> {
  const [actor, waiter] = await getActorAndWaiter(alicePage, bobPage);

  if (isPreflop) {
    await performAction(actor, 'call');
    await expect(async () => {
      expect(await isMyTurn(waiter)).toBe(true);
    }).toPass({ timeout: 10000 });
    await performAction(waiter, 'check');
  } else {
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

test.describe('Omaha Poker', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('2 players see 4 hole cards each', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Omaha ${Date.now()}`,
      variant: 'omaha',
      maxPlayers: 6,
    });
    await joinTableByName(bobPage, tableName);

    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
    await expect(bobPage.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    // Each player should see 4 face-up cards in their own hand
    // Current player's cards are rendered with rank/suit (face-up)
    await expect(async () => {
      const aliceCards = alicePage.locator('.player-cards .card');
      const count = await aliceCards.count();
      expect(count).toBeGreaterThanOrEqual(4);
    }).toPass({ timeout: 10000 });

    await expect(async () => {
      const bobCards = bobPage.locator('.player-cards .card');
      const count = await bobCards.count();
      expect(count).toBeGreaterThanOrEqual(4);
    }).toPass({ timeout: 10000 });

    // Pot should be $3 (blinds: $1 SB + $2 BB)
    const pot = await getPotAmount(alicePage);
    expect(pot).toBe(3);
  });

  test('opponent shows 4 card backs', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Omaha Backs ${Date.now()}`,
      variant: 'omaha',
      maxPlayers: 6,
    });
    await joinTableByName(bobPage, tableName);

    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Alice should see bob's cards as card-backs
    // Opponents' face-down cards render with class "card card-back"
    await expect(async () => {
      const opponentSeat = alicePage.locator('.player-seat:has(.player-name:has-text("bob"))');
      const cardBacks = opponentSeat.locator('.player-cards .card-back');
      const count = await cardBacks.count();
      expect(count).toBe(4);
    }).toPass({ timeout: 10000 });
  });

  test('4 cards use many-cards class', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Omaha CSS ${Date.now()}`,
      variant: 'omaha',
      maxPlayers: 6,
    });
    await joinTableByName(bobPage, tableName);

    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // The player-cards container should have the many-cards class for 4 cards
    await expect(async () => {
      const manyCardsContainers = alicePage.locator('.player-cards.many-cards');
      const count = await manyCardsContainers.count();
      expect(count).toBeGreaterThanOrEqual(1);
    }).toPass({ timeout: 10000 });
  });

  test('full Omaha hand plays to showdown', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Omaha Full ${Date.now()}`,
      variant: 'omaha',
      maxPlayers: 6,
    });
    await joinTableByName(bobPage, tableName);

    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
    await expect(bobPage.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    // Preflop: SB calls, BB checks
    await playCheckCallRound(alicePage, bobPage, true);

    // Flop: 3 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    await playCheckCallRound(alicePage, bobPage);

    // Turn: 4 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(4);
    }).toPass({ timeout: 10000 });

    await playCheckCallRound(alicePage, bobPage);

    // River: 5 community cards
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(5);
    }).toPass({ timeout: 10000 });

    await playCheckCallRound(alicePage, bobPage);

    // Showdown: results should appear
    await expect(async () => {
      const showdown = alicePage.locator('#showdown-results-container');
      expect(await showdown.isVisible()).toBe(true);
    }).toPass({ timeout: 15000 });

    await expect(async () => {
      const showdown = bobPage.locator('#showdown-results-container');
      expect(await showdown.isVisible()).toBe(true);
    }).toPass({ timeout: 5000 });

    // Chat should show showdown messages
    await expect(alicePage.locator('#chat-messages:has-text("SHOW DOWN")')).toBeVisible({ timeout: 5000 });
    const chatText = await alicePage.locator('#chat-messages').textContent();
    expect(chatText).toMatch(/wins with|collected|split/);
  });
});
