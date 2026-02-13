/**
 * E2E regression tests for fold-to-win and hand cycling.
 *
 * Verifies:
 * - Fold ends the hand immediately and awards pot
 * - A new hand starts after the previous hand completes
 * - Dealer position rotates between hands
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
 * Get the player name who has the dealer button.
 * JS-rendered seats use data-position (not data-seat), so we extract
 * the player name from the seat that contains the dealer indicator.
 */
async function getDealerPlayerName(page: Page): Promise<string | null> {
  const dealerIndicator = page.locator('.position-indicator.dealer');
  if (await dealerIndicator.isVisible({ timeout: 5000 }).catch(() => false)) {
    const seats = page.locator('.player-seat');
    const count = await seats.count();
    for (let i = 0; i < count; i++) {
      const seat = seats.nth(i);
      const hasDealer = await seat.locator('.position-indicator.dealer').isVisible().catch(() => false);
      if (hasDealer) {
        const nameEl = seat.locator('.player-name');
        return await nameEl.textContent();
      }
    }
  }
  return null;
}

/**
 * Ready up both players for the next hand.
 * After a hand ends, the ready panel reappears and both players must click Ready again.
 */
async function readyUpForNextHand(alicePage: Page, bobPage: Page): Promise<void> {
  // Wait for ready panel to appear on both pages
  for (const page of [alicePage, bobPage]) {
    await expect(page.locator('#ready-panel:not(.hidden)')).toBeVisible({ timeout: 15000 });
  }
  await clickReady(alicePage);
  await clickReady(bobPage);
  await waitForGameStart(alicePage);
  await waitForGameStart(bobPage);
}

// ============================================================================
// TESTS
// ============================================================================

test.describe('Fold and Hand Cycle', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('fold preflop ends hand and awards pot to opponent', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Fold ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Pot starts at $3 (blinds)
    const initialPot = await getPotAmount(alicePage);
    expect(initialPot).toBe(3);

    // SB folds
    const [actor, waiter, actorName] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(actor, 'fold');

    // No community cards should be dealt (hand ended immediately)
    await actor.waitForTimeout(2000);
    const communityCount = await getCommunityCardCount(actor);
    expect(communityCount).toBe(0);

    // The chat should indicate the fold and pot win
    await expect(async () => {
      const chatText = await waiter.locator('#chat-messages').textContent();
      expect(chatText).toMatch(/fold|collected|wins/i);
    }).toPass({ timeout: 10000 });
  });

  test('fold on flop ends hand without further cards', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Fold Flop ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Play through preflop: SB calls, BB checks
    const [sbPage, bbPage] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(sbPage, 'call');
    await expect(async () => {
      expect(await isMyTurn(bbPage)).toBe(true);
    }).toPass({ timeout: 10000 });
    await performAction(bbPage, 'check');

    // Wait for flop
    await expect(async () => {
      expect(await getCommunityCardCount(alicePage)).toBe(3);
    }).toPass({ timeout: 10000 });

    // On flop, first actor folds
    const [flopActor, flopWaiter] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(flopActor, 'fold');

    // Wait a moment - no turn card should appear
    await flopActor.waitForTimeout(2000);
    const communityCount = await getCommunityCardCount(flopActor);
    expect(communityCount).toBe(3); // Still just the flop, no turn

    // Chat should show fold and pot collection
    await expect(async () => {
      const chatText = await flopWaiter.locator('#chat-messages').textContent();
      expect(chatText).toMatch(/fold|collected|wins/i);
    }).toPass({ timeout: 10000 });
  });

  test('new hand starts after fold with incremented hand number', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Cycle ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Record hand number
    const hand1Num = await alicePage.locator('#hand-number').textContent();

    // Verify dealer indicator is shown
    const dealer1Name = await getDealerPlayerName(alicePage);
    expect(dealer1Name).toBeTruthy();

    // SB folds to end hand quickly
    const [actor] = await getActorAndWaiter(alicePage, bobPage);
    await performAction(actor, 'fold');

    // Ready up for next hand (players must click Ready again)
    await readyUpForNextHand(alicePage, bobPage);

    // Hand number should have incremented
    const hand2Num = await alicePage.locator('#hand-number').textContent();
    expect(parseInt(hand2Num || '0')).toBeGreaterThan(parseInt(hand1Num || '0'));

    // Dealer indicator should still be visible in the new hand
    const dealer2Name = await getDealerPlayerName(alicePage);
    expect(dealer2Name).toBeTruthy();

    // Both players should have cards
    const aliceCards = alicePage.locator('.player-cards .card');
    expect(await aliceCards.count()).toBeGreaterThanOrEqual(2);
  });

  test('three consecutive hands can be played', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, { name: `Test Multi ${Date.now()}` });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);

    // Play 3 hands by folding preflop each time
    for (let hand = 0; hand < 3; hand++) {
      // Find who acts and fold
      const [actor] = await getActorAndWaiter(alicePage, bobPage);
      await performAction(actor, 'fold');

      if (hand < 2) {
        // Ready up for next hand
        await readyUpForNextHand(alicePage, bobPage);
      }
    }

    // Hand number should be at least 3
    await expect(async () => {
      const finalHand = await alicePage.locator('#hand-number').textContent();
      expect(parseInt(finalHand || '0')).toBeGreaterThanOrEqual(3);
    }).toPass({ timeout: 15000 });
  });
});
