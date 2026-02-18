/**
 * Tier 1: Parametrized variant smoke tests.
 *
 * Plays a full hand passively (check/call/stand-pat) for 25 representative
 * variants covering every interaction pattern: betting, bring-in, draw,
 * discard, expose, separate, declare, choose, and various community layouts.
 */
import {
  test,
  expect,
  createTable,
  joinTableByName,
  clickReady,
  waitForGameStart,
  callCleanupApi,
  cleanupTestTables,
  playHandPassively,
  TIER_1_VARIANTS,
  VariantTestConfig,
} from '../helpers';

test.describe('Variant Smoke Tests', () => {
  // Stud/draw games with many rounds can take longer
  test.setTimeout(120000);

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
    // Brief wait for server to settle after cleanup
    await alicePage.waitForTimeout(500);
  });

  for (const variant of TIER_1_VARIANTS) {
    test(`${variant.displayName} plays to completion`, async ({ alicePage, bobPage }) => {
      // Build table config based on variant
      const tableConfig: any = {
        name: `Test ${variant.displayName} ${Date.now()}`,
        variant: variant.variant,
        bettingStructure: variant.bettingStructure,
        maxPlayers: variant.maxPlayers || 6,
      };

      // Set stakes based on betting structure
      if (variant.bettingStructure === 'Limit') {
        if (variant.forcedBetStyle === 'bring-in') {
          tableConfig.smallBet = 10;
          tableConfig.bigBet = 20;
          tableConfig.ante = 2;
        } else {
          tableConfig.smallBet = 2;
          tableConfig.bigBet = 4;
        }
      } else {
        tableConfig.smallBlind = 1;
        tableConfig.bigBlind = 2;
      }

      const tableName = await createTable(alicePage, tableConfig);
      // Use higher buy-in for high-stakes Limit tables
      const buyIn = (variant.bettingStructure === 'Limit' && variant.forcedBetStyle === 'bring-in') ? 400 : 80;
      await joinTableByName(bobPage, tableName, { buyIn });

      // Wait for both players visible
      await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });
      await expect(bobPage.locator('.player-name:has-text("alice")')).toBeVisible({ timeout: 10000 });

      // Ready up
      await clickReady(alicePage);
      await clickReady(bobPage);
      await waitForGameStart(alicePage);
      await waitForGameStart(bobPage);

      // Play the hand passively
      const result = await playHandPassively(
        [{ page: alicePage, name: 'alice' }, { page: bobPage, name: 'bob' }],
        { maxActions: 200, timeout: 90000 }
      );

      expect(result.completed, `Hand did not complete after ${result.actions} actions: ${result.error || 'unknown'}`).toBe(true);
    });
  }
});
