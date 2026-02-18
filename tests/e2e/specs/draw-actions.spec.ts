/**
 * Tier 2: Draw/discard UI verification tests.
 *
 * Verifies that draw-related action controls render correctly:
 * - Stand pat button text
 * - Selectable cards
 * - Multiple draw rounds
 * - Forced discard
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
  isMyAction,
  getValidActionTypes,
  PlayerHandle,
} from '../helpers';

test.describe('Draw Action UI', () => {

  test.beforeEach(async ({ alicePage }) => {
    await callCleanupApi(alicePage);
    await cleanupTestTables();
  });

  test('Five Card Draw: stand pat button and selectable cards', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test 5CD ${Date.now()}`,
      variant: '5_card_draw',
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

    // Play through the pre-draw betting round (check/call)
    // Keep performing passive actions until we see a draw action
    let drawFound = false;
    for (let i = 0; i < 20; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('draw')) {
        drawFound = true;

        // Verify draw UI elements
        const submitBtn = active.actor.locator('.draw-submit-btn');
        await expect(submitBtn).toBeAttached({ timeout: 5000 });

        // Button should say "Stand Pat" when no cards selected (min=0)
        const btnText = await submitBtn.textContent();
        expect(btnText).toContain('Stand Pat');

        // Selectable cards should be present
        const selectableCards = active.actor.locator('.card.selectable');
        const cardCount = await selectableCards.count();
        expect(cardCount).toBeGreaterThan(0);

        // Submit should be enabled (stand pat is valid)
        expect(await submitBtn.isDisabled()).toBe(false);
        break;
      }

      await performPassiveAction(active.actor);
    }

    expect(drawFound).toBe(true);
  });

  test('Badugi: multiple draw rounds appear', async ({ alicePage, bobPage }) => {
    test.setTimeout(120000);
    const tableName = await createTable(alicePage, {
      name: `Test Badugi ${Date.now()}`,
      variant: 'badugi',
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

    // Play passively and count how many draw rounds we encounter
    let drawRounds = 0;
    for (let i = 0; i < 100; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      // Check for hand completion
      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('draw')) {
        drawRounds++;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    // Badugi has 3 draw rounds — each player gets to draw in each
    // With 2 players, we should see at least 2 draw actions (one per player per round)
    expect(drawRounds).toBeGreaterThanOrEqual(2);
  });

  test('Crazy Pineapple: forced discard after flop', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test CrazyP ${Date.now()}`,
      variant: 'crazy_pineapple',
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

    // Play through to find a discard action
    let discardFound = false;
    for (let i = 0; i < 30; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('discard')) {
        discardFound = true;

        // Verify discard UI — submit button should be present
        const submitBtn = active.actor.locator('.draw-submit-btn');
        await expect(submitBtn).toBeAttached({ timeout: 5000 });

        // Selectable cards should be present
        const selectableCards = active.actor.locator('.card.selectable');
        expect(await selectableCards.count()).toBeGreaterThan(0);
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(discardFound).toBe(true);
  });

  test('Dramaha: draw phase after community cards', async ({ alicePage, bobPage }) => {
    const tableName = await createTable(alicePage, {
      name: `Test Dramaha ${Date.now()}`,
      variant: 'dramaha',
      bettingStructure: 'Pot-Limit',
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

    // Play through to find a draw action — Dramaha has draw after community betting
    let drawFound = false;
    for (let i = 0; i < 40; i++) {
      const active = await getActivePlayer(players);
      if (!active) break;

      const readyPanel = players[0].page.locator('#ready-panel:not(.hidden)');
      if (await readyPanel.isVisible().catch(() => false)) break;

      const actionTypes = await getValidActionTypes(active.actor);
      if (actionTypes.includes('draw')) {
        drawFound = true;

        // Verify draw controls appear
        const submitBtn = active.actor.locator('.draw-submit-btn');
        await expect(submitBtn).toBeAttached({ timeout: 5000 });
        break;
      }

      await performPassiveAction(active.actor);
      await players[0].page.waitForTimeout(300);
    }

    expect(drawFound).toBe(true);
  });
});
