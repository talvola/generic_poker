/**
 * E2E tests for 3-player Texas Hold'em.
 *
 * Verifies that the engine, WebSocket layer, and UI all work correctly
 * with 3 players: joining, position assignment (D/SB/BB on separate seats),
 * fold continuation, and full hand to showdown.
 *
 * Uses a 6-max table (CSS already exists) with alice, bob, charlie.
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
  getActor,
  PlayerHandle,
  BASE_URL,
} from '../helpers';

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Set up a 3-player game: create 6-max table, all join, all ready, wait for deal.
 * Returns the table name and player handles array.
 */
async function setup3PlayerGame(
  alicePage: Page,
  bobPage: Page,
  charliePage: Page
): Promise<{ tableName: string; players: PlayerHandle[] }> {
  const tableName = await createTable(alicePage, {
    name: `Test 3P ${Date.now()}`,
    maxPlayers: 6,
  });

  // Bob and Charlie join
  await joinTableByName(bobPage, tableName);
  await joinTableByName(charliePage, tableName);

  // Wait for all 3 players to see each other
  for (const page of [alicePage, bobPage, charliePage]) {
    await expect(page.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.player-name:has-text("charlie")')).toBeVisible({ timeout: 10000 });
  }

  // All ready up
  await clickReady(alicePage);
  await clickReady(bobPage);
  await clickReady(charliePage);

  // Wait for game to start on all pages
  await waitForGameStart(alicePage);
  await waitForGameStart(bobPage);
  await waitForGameStart(charliePage);

  const players: PlayerHandle[] = [
    { page: alicePage, name: 'alice' },
    { page: bobPage, name: 'bob' },
    { page: charliePage, name: 'charlie' },
  ];

  return { tableName, players };
}

/**
 * Play a preflop round in 3-player Hold'em.
 * Preflop order: UTG (dealer/button) acts first, then SB, then BB.
 * Each player either calls or checks as appropriate.
 */
async function playPreflopCallAround(players: PlayerHandle[]): Promise<void> {
  // UTG (button) acts first preflop in 3-player - calls
  let result = await getActor(players);
  await performAction(result.actor, 'call');

  // SB acts next - calls
  await expect(async () => {
    result = await getActor(players);
  }).toPass({ timeout: 10000 });
  await performAction(result.actor, 'call');

  // BB acts last - checks
  await expect(async () => {
    result = await getActor(players);
  }).toPass({ timeout: 10000 });
  await performAction(result.actor, 'check');
}

/**
 * Play a post-flop check-around for 3 active players.
 */
async function playCheckAround(players: PlayerHandle[]): Promise<void> {
  for (let i = 0; i < players.length; i++) {
    const result = await getActor(players);
    await performAction(result.actor, 'check');
    if (i < players.length - 1) {
      // Wait for next player to get action
      await result.others[0].waitForTimeout(500);
    }
  }
}

// ============================================================================
// TESTS
// ============================================================================

test.describe('Three Player Hold\'em', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('3 players join, ready, and start hand', async ({ alicePage, bobPage, charliePage }) => {
    const { players } = await setup3PlayerGame(alicePage, bobPage, charliePage);

    // All 3 players should see 3 player seats with names
    for (const player of players) {
      const playerNames = player.page.locator('.player-name');
      const count = await playerNames.count();
      expect(count).toBeGreaterThanOrEqual(3);
    }

    // Each player should see hole cards
    for (const player of players) {
      const cards = player.page.locator('.player-cards .card');
      expect(await cards.count()).toBeGreaterThanOrEqual(2);
    }

    // Pot should be $3 (SB $1 + BB $2)
    const pot = await getPotAmount(alicePage);
    expect(pot).toBe(3);

    // No community cards yet
    const communityCount = await getCommunityCardCount(alicePage);
    expect(communityCount).toBe(0);
  });

  test('D, SB, BB shown on 3 different seats', async ({ alicePage, bobPage, charliePage }) => {
    await setup3PlayerGame(alicePage, bobPage, charliePage);

    // Check for 3 distinct position indicators on alice's view
    const dealerIndicators = alicePage.locator('.position-indicator.dealer');
    const sbIndicators = alicePage.locator('.position-indicator.small-blind');
    const bbIndicators = alicePage.locator('.position-indicator.big-blind');

    await expect(dealerIndicators).toHaveCount(1, { timeout: 5000 });
    await expect(sbIndicators).toHaveCount(1, { timeout: 5000 });
    await expect(bbIndicators).toHaveCount(1, { timeout: 5000 });

    // All 3 should be on different player seats
    const seats = alicePage.locator('.player-seat');
    const seatCount = await seats.count();
    const positionsWithIndicators: string[] = [];

    for (let i = 0; i < seatCount; i++) {
      const seat = seats.nth(i);
      const hasDealer = await seat.locator('.position-indicator.dealer').isVisible().catch(() => false);
      const hasSB = await seat.locator('.position-indicator.small-blind').isVisible().catch(() => false);
      const hasBB = await seat.locator('.position-indicator.big-blind').isVisible().catch(() => false);

      if (hasDealer || hasSB || hasBB) {
        const pos = await seat.getAttribute('data-position');
        positionsWithIndicators.push(pos || '');
      }
    }

    // Should have 3 distinct positions
    expect(new Set(positionsWithIndicators).size).toBe(3);
  });

  test('one player folds, remaining two continue to flop', async ({ alicePage, bobPage, charliePage }) => {
    const { players } = await setup3PlayerGame(alicePage, bobPage, charliePage);

    // First actor (UTG/button preflop) folds
    const result = await getActor(players);
    const folderName = result.actorName;
    await performAction(result.actor, 'fold');

    // Remaining two players: one calls, one checks
    const remaining = players.filter(p => p.name !== folderName);

    // Next actor calls (SB)
    let nextResult = await getActor(remaining);
    await performAction(nextResult.actor, 'call');

    // Last actor checks (BB)
    await expect(async () => {
      nextResult = await getActor(remaining);
    }).toPass({ timeout: 10000 });
    await performAction(nextResult.actor, 'check');

    // Flop should be dealt
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    // Pot should be $4 ($1 SB completed + $2 BB = $4 total with SB call)
    await expect(async () => {
      const pot = await getPotAmount(alicePage);
      expect(pot).toBe(4);
    }).toPass({ timeout: 5000 });

    // The folded player's seat should show folded styling
    const folderSeat = alicePage.locator(`.player-info.folded:has(.player-name:has-text("${folderName}"))`);
    await expect(folderSeat).toBeVisible({ timeout: 5000 });
  });

  test('full 3-player hand to showdown', async ({ alicePage, bobPage, charliePage }) => {
    const { players } = await setup3PlayerGame(alicePage, bobPage, charliePage);

    // === PREFLOP ===
    // UTG calls, SB calls, BB checks
    await playPreflopCallAround(players);

    // === FLOP ===
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(3);
    }).toPass({ timeout: 10000 });

    // All 3 check
    await playCheckAround(players);

    // === TURN ===
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(4);
    }).toPass({ timeout: 10000 });

    // All 3 check
    await playCheckAround(players);

    // === RIVER ===
    await expect(async () => {
      const count = await getCommunityCardCount(alicePage);
      expect(count).toBe(5);
    }).toPass({ timeout: 10000 });

    // All 3 check
    await playCheckAround(players);

    // === SHOWDOWN ===
    await expect(async () => {
      const showdownContainer = alicePage.locator('#showdown-results-container');
      const isVisible = await showdownContainer.isVisible();
      expect(isVisible).toBe(true);
    }).toPass({ timeout: 15000 });

    // All players should see showdown results
    for (const player of players) {
      await expect(async () => {
        const showdownContainer = player.page.locator('#showdown-results-container');
        const isVisible = await showdownContainer.isVisible();
        expect(isVisible).toBe(true);
      }).toPass({ timeout: 5000 });
    }

    // Chat should mention showdown and winner
    const chatText = await alicePage.locator('#chat-messages').textContent();
    expect(chatText).toMatch(/SHOW DOWN/);
    expect(chatText).toMatch(/wins with|collected|split/);
  });
});
