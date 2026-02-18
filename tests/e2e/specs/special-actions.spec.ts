/**
 * Tier 2: Special action UI verification tests.
 *
 * Verifies non-standard action controls render correctly:
 * - Declare buttons with data-declaration attributes
 * - Expose phase with selectable face-down cards
 * - Separate subsets with subset tags
 * - Choose buttons with game variant options
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
  getActivePlayer,
  performPassiveAction,
  getValidActionTypes,
  PlayerHandle,
} from '../helpers';

test.describe('Special Action UI', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('Straight Declare: declare buttons appear', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Declare ${Date.now()}`,
      variant: 'straight_declare',
      bettingStructure: 'No-Limit',
      maxPlayers: 6,
      smallBlind: 1,
      bigBlind: 2,
    });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    const players: PlayerHandle[] = [
      { page: alicePage, name: 'alice' },
      { page: bobPage, name: 'bob' },
    ];

    // Play through to find a declare action
    let declareFound = false;
    for (let i = 0; i < 30; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('declare')) {
        declareFound = true;

        // Verify declare buttons
        const declareBtns = active.actor.locator('.declare-btn');
        const btnCount = await declareBtns.count();
        expect(btnCount).toBeGreaterThanOrEqual(2); // At least high and low

        // Buttons should have data-declaration attributes
        for (let j = 0; j < btnCount; j++) {
          const attr = await declareBtns.nth(j).getAttribute('data-declaration');
          expect(attr).toBeTruthy();
        }
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(declareFound).toBe(true);
  });

  test('Showmaha: expose phase with selectable cards', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Expose ${Date.now()}`,
      variant: 'showmaha',
      bettingStructure: 'No-Limit',
      maxPlayers: 6,
      smallBlind: 1,
      bigBlind: 2,
    });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    const players: PlayerHandle[] = [
      { page: alicePage, name: 'alice' },
      { page: bobPage, name: 'bob' },
    ];

    // Play through to find an expose action
    let exposeFound = false;
    for (let i = 0; i < 30; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('expose')) {
        exposeFound = true;

        // Verify expose UI — submit button and selectable cards
        const submitBtn = active.actor.locator('.draw-submit-btn');
        await expect(submitBtn).toBeAttached({ timeout: 5000 });

        // Button text should reference "expose"
        const btnText = await submitBtn.textContent();
        expect(btnText?.toLowerCase()).toContain('expose');

        // Selectable cards should be present
        const selectableCards = active.actor.locator('.card.selectable');
        expect(await selectableCards.count()).toBeGreaterThan(0);
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(exposeFound).toBe(true);
  });

  test('SOHE: separate subsets UI', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Separate ${Date.now()}`,
      variant: 'sohe',
      bettingStructure: 'Limit',
      maxPlayers: 6,
      smallBet: 2,
      bigBet: 4,
    });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    const players: PlayerHandle[] = [
      { page: alicePage, name: 'alice' },
      { page: bobPage, name: 'bob' },
    ];

    // Play through to find a separate action
    let separateFound = false;
    for (let i = 0; i < 30; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('separate')) {
        separateFound = true;

        // Verify separate UI — subset tags should be visible
        const subsetTags = active.actor.locator('.subset-tag');
        expect(await subsetTags.count()).toBeGreaterThanOrEqual(2);

        // Reset button should exist
        const resetBtn = active.actor.locator('.separate-reset-btn');
        await expect(resetBtn).toBeAttached({ timeout: 5000 });

        // Submit button (Separate) should exist
        const submitBtn = active.actor.locator('.draw-submit-btn');
        await expect(submitBtn).toBeAttached({ timeout: 5000 });
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(separateFound).toBe(true);
  });

  test("Paradise Road Pick'em: choose buttons", async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Choose ${Date.now()}`,
      variant: 'paradise_road_pickem',
      bettingStructure: 'Limit',
      maxPlayers: 2,
      smallBet: 2,
      bigBet: 4,
    });
    await joinTableByName(bobPage, tableName);
    await expect(alicePage.locator('.player-name:has-text("bob")')).toBeVisible({ timeout: 10000 });

    await clickReady(alicePage);
    await clickReady(bobPage);
    await waitForGameStart(alicePage);
    await waitForGameStart(bobPage);

    const players: PlayerHandle[] = [
      { page: alicePage, name: 'alice' },
      { page: bobPage, name: 'bob' },
    ];

    // Play through to find a choose action
    let chooseFound = false;
    for (let i = 0; i < 30; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('choose')) {
        chooseFound = true;

        // Verify choose buttons
        const chooseBtns = active.actor.locator('.choose-btn');
        const btnCount = await chooseBtns.count();
        expect(btnCount).toBeGreaterThanOrEqual(2);

        // Buttons should have data-choice-index attributes
        for (let j = 0; j < btnCount; j++) {
          const attr = await chooseBtns.nth(j).getAttribute('data-choice-index');
          expect(attr).toBeTruthy();
        }
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(chooseFound).toBe(true);
  });
});
