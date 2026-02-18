/**
 * E2E Test Helpers for Game Actions
 *
 * Reusable helper functions for N-player game flow.
 */

import { Page } from '@playwright/test';
import { isMyTurn, isMyAction, getValidActionTypes, performAction } from './table-helpers';

export interface PlayerHandle {
  page: Page;
  name: string;
}

export interface ActorResult {
  actor: Page;
  actorName: string;
  others: Page[];
}

/**
 * Determine which player is the current actor (has enabled betting action buttons).
 * Works for any number of players. Polls all pages until one has action buttons.
 */
export async function getActor(players: PlayerHandle[]): Promise<ActorResult> {
  for (let i = 0; i < 20; i++) {
    for (const player of players) {
      const hasActions = await isMyTurn(player.page);
      if (hasActions) {
        return {
          actor: player.page,
          actorName: player.name,
          others: players.filter(p => p.name !== player.name).map(p => p.page),
        };
      }
    }
    await players[0].page.waitForTimeout(500);
  }
  throw new Error(`No player has action buttons after 10 seconds (players: ${players.map(p => p.name).join(', ')})`);
}

/**
 * Check if the game has completed by examining the client-side store.
 * Returns true if game_phase is 'showdown', 'complete', or 'waiting' (after hand).
 */
async function isHandComplete(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    const pt = (window as any).pokerTable;
    const phase = pt?.store?.gameState?.game_phase || '';
    // Check store state
    if (phase === 'showdown' || phase === 'complete') return true;
    // Also check if ready panel is visible via DOM
    const readyPanel = document.querySelector('#ready-panel:not(.hidden)');
    if (readyPanel) return true;
    // Check if showdown container is visible
    const showdown = document.querySelector('#showdown-results-container');
    if (showdown && (showdown as HTMLElement).offsetParent !== null) return true;
    return false;
  });
}

/**
 * Determine which player has ANY action to perform (betting, draw, declare, choose, etc.)
 * Polls all pages until one has any action control visible.
 * Also checks for hand completion during polling to avoid 10s timeout.
 */
export async function getActivePlayer(players: PlayerHandle[]): Promise<ActorResult | null> {
  for (let i = 0; i < 20; i++) {
    for (const player of players) {
      const hasAction = await isMyAction(player.page);
      if (hasAction) {
        return {
          actor: player.page,
          actorName: player.name,
          others: players.filter(p => p.name !== player.name).map(p => p.page),
        };
      }
    }
    // Check if hand completed while polling (avoids 10s timeout at end of hand)
    for (const player of players) {
      if (await isHandComplete(player.page)) {
        return null; // Signal caller to check completion
      }
    }
    await players[0].page.waitForTimeout(500);
  }
  return null;
}

// ============================================================================
// PASSIVE ACTION HANDLERS
// ============================================================================

/**
 * Click the minimum number of selectable cards needed to enable submit.
 * Used for draw/discard/expose/pass actions.
 */
async function selectMinimumCards(page: Page): Promise<void> {
  // Check if submit is already enabled (min=0, stand pat)
  const submitBtn = page.locator('.draw-submit-btn');
  if (await submitBtn.count() > 0 && !(await submitBtn.isDisabled())) {
    return; // Already enabled — stand pat
  }

  // Click selectable cards one at a time until submit enables
  const selectableCards = page.locator('.card.selectable:not(.selected)');
  const cardCount = await selectableCards.count();

  for (let i = 0; i < cardCount; i++) {
    // Re-query because DOM may change after each click
    const card = page.locator('.card.selectable:not(.selected)').first();
    if (await card.count() === 0) break;
    try {
      await card.click({ timeout: 3000 });
    } catch {
      // Card may have been detached by DOM update, retry from loop
      continue;
    }
    await page.waitForTimeout(200);

    // Check if submit button is now enabled
    const btn = page.locator('.draw-submit-btn');
    if (await btn.count() > 0 && !(await btn.isDisabled())) {
      return;
    }
  }
}

/**
 * Fill all subsets in a separate action by clicking cards in order.
 * The UI auto-assigns cards to subsets as you click them.
 */
async function fillSeparateSubsets(page: Page): Promise<void> {
  // Click all selectable cards in order — UI auto-assigns to subsets
  for (let attempt = 0; attempt < 20; attempt++) {
    const card = page.locator('.card.selectable:not(.selected)').first();
    if (await card.count() === 0) break;
    try {
      await card.click({ timeout: 3000 });
    } catch {
      continue;
    }
    await page.waitForTimeout(200);

    // Check if submit is enabled
    const btn = page.locator('.draw-submit-btn');
    if (await btn.count() > 0 && !(await btn.isDisabled())) {
      return;
    }
  }
}

/**
 * Try to find and click an actionable control on the page.
 * Returns the action type string if successful, or null if no control found.
 */
async function tryPerformAction(page: Page): Promise<string | null> {
  // Helper to safely click a button that may detach between count() and click()
  const safeClick = async (locator: any, label: string): Promise<string | null> => {
    try {
      if (await locator.count() > 0) {
        await locator.click({ timeout: 3000 });
        return label;
      }
    } catch {
      return null; // Element detached — retry from main loop
    }
    return '__skip__';
  };

  // Bring-in button (stud games — server labels it "Bring_In")
  const bringIn = await safeClick(
    page.locator('.action-btn:has-text("Bring_In"):not([disabled]), .action-btn:has-text("Bring In"):not([disabled])').first(),
    'bring_in'
  );
  if (bringIn === null) return null;
  if (bringIn !== '__skip__') return bringIn;

  // Check button (free action, highest priority)
  const check = await safeClick(page.locator('button:has-text("Check"):not([disabled])').first(), 'check');
  if (check === null) return null;
  if (check !== '__skip__') return check;

  // Call button
  const call = await safeClick(page.locator('button:has-text("Call"):not([disabled])').first(), 'call');
  if (call === null) return null;
  if (call !== '__skip__') return call;

  // Complete button (bring-in completion)
  const complete = await safeClick(page.locator('.action-btn:has-text("Complete"):not([disabled])').first(), 'complete');
  if (complete === null) return null;
  if (complete !== '__skip__') return complete;

  // Draw/discard/expose/pass submit button
  const drawSubmitBtn = page.locator('.draw-submit-btn');
  if (await drawSubmitBtn.count() > 0) {
    try {
      if (!(await drawSubmitBtn.isDisabled())) {
        await drawSubmitBtn.click({ timeout: 3000 });
        return 'draw';
      }
    } catch {
      // Element may have detached between count() and isDisabled() — retry from loop
      return null;
    }
    // Need to select cards first
    try {
      await selectMinimumCards(page);
      const submitBtn = page.locator('.draw-submit-btn:not([disabled])');
      if (await submitBtn.count() > 0) {
        await submitBtn.click({ timeout: 3000 });
        return 'draw';
      }
    } catch {
      return null;
    }
  }

  // Separate controls (with subset tags)
  const subsetTags = page.locator('.subset-tag');
  if (await subsetTags.count() > 0) {
    try {
      await fillSeparateSubsets(page);
      const submitBtn = page.locator('.draw-submit-btn:not([disabled])');
      if (await submitBtn.count() > 0) {
        await submitBtn.click({ timeout: 3000 });
        return 'separate';
      }
    } catch {
      return null;
    }
  }

  // Declare buttons
  const declare = await safeClick(page.locator('.declare-btn:not([disabled])').first(), 'declare');
  if (declare === null) return null;
  if (declare !== '__skip__') return declare;

  // Choose buttons
  const choose = await safeClick(page.locator('.choose-btn:not([disabled])').first(), 'choose');
  if (choose === null) return null;
  if (choose !== '__skip__') return choose;

  // Fold button (last resort)
  const fold = await safeClick(page.locator('button:has-text("Fold"):not([disabled])').first(), 'fold');
  if (fold === null) return null;
  if (fold !== '__skip__') return fold;

  // Any enabled action button
  const fallback = await safeClick(page.locator('.action-btn:not([disabled])').first(), 'fallback');
  if (fallback === null) return null;
  if (fallback !== '__skip__') return fallback;

  return null;
}

/**
 * Perform the most passive action available on the page.
 * Handles all action types: betting, draw, declare, choose, etc.
 *
 * Uses a DOM-first approach with retry: polls the page for actionable controls,
 * retrying if the DOM hasn't updated yet after a state change.
 *
 * Returns the action type that was performed.
 */
export async function performPassiveAction(page: Page): Promise<string | null> {
  // Retry loop: DOM may not have caught up with state changes yet
  for (let attempt = 0; attempt < 10; attempt++) {
    // Check if we're still showing "Waiting for your turn..."
    const waitingMsg = page.locator('.waiting-message');
    if (await waitingMsg.count() > 0) {
      await page.waitForTimeout(300);
      continue;
    }

    const result = await tryPerformAction(page);
    if (result) {
      await page.waitForTimeout(500);
      return result;
    }

    // No controls found yet — wait and retry
    await page.waitForTimeout(500);
  }

  // No controls found after retries — state may have changed, let caller retry
  return null;
}

// ============================================================================
// FULL HAND PLAY
// ============================================================================

export interface PlayHandOptions {
  maxActions?: number;
  timeout?: number;
}

export interface PlayResult {
  completed: boolean;
  actions: number;
  error?: string;
}

/**
 * Play a full hand passively — all players check/call/stand-pat through completion.
 * Handles all action types (betting, draw, declare, choose, expose, separate, pass).
 * Returns when the hand completes (showdown or fold win) or max actions/timeout reached.
 */
export async function playHandPassively(
  players: PlayerHandle[],
  options: PlayHandOptions = {}
): Promise<PlayResult> {
  const maxActions = options.maxActions || 200;
  const timeout = options.timeout || 45000;
  let actionCount = 0;
  const startTime = Date.now();

  while (actionCount < maxActions && (Date.now() - startTime) < timeout) {
    // Check for hand completion on any player's page
    const firstPage = players[0].page;

    // Check if ready panel appeared (hand ended, waiting for next)
    const readyPanel = firstPage.locator('#ready-panel:not(.hidden)');
    if (await readyPanel.isVisible().catch(() => false)) {
      return { completed: true, actions: actionCount };
    }

    // Check showdown results
    const showdown = firstPage.locator('#showdown-results-container');
    if (await showdown.isVisible().catch(() => false)) {
      return { completed: true, actions: actionCount };
    }

    // Find the active player
    const active = await getActivePlayer(players);
    if (!active) {
      // No player has actions — check completion on ALL pages (store-based + DOM)
      for (const player of players) {
        if (await isHandComplete(player.page)) {
          return { completed: true, actions: actionCount };
        }
      }
      // DOM-based fallback checks
      const readyNow = firstPage.locator('#ready-panel:not(.hidden)');
      if (await readyNow.isVisible().catch(() => false)) {
        return { completed: true, actions: actionCount };
      }
      const showdownNow = firstPage.locator('#showdown-results-container');
      if (await showdownNow.isVisible().catch(() => false)) {
        return { completed: true, actions: actionCount };
      }
      // Timed out waiting for any player's turn
      return { completed: false, actions: actionCount, error: 'No player received actions within 10s polling window' };
    }

    try {
      const actionResult = await performPassiveAction(active.actor);
      if (actionResult) {
        actionCount++;
      }
      // If null, state changed — just retry the loop
    } catch (e: any) {
      return { completed: false, actions: actionCount, error: e.message };
    }

    // Brief wait for WebSocket propagation
    await firstPage.waitForTimeout(300);
  }

  // Check one final time if completed
  const firstPage = players[0].page;
  const readyFinal = firstPage.locator('#ready-panel:not(.hidden)');
  if (await readyFinal.isVisible().catch(() => false)) {
    return { completed: true, actions: actionCount };
  }
  const showdownFinal = firstPage.locator('#showdown-results-container');
  if (await showdownFinal.isVisible().catch(() => false)) {
    return { completed: true, actions: actionCount };
  }

  return {
    completed: false,
    actions: actionCount,
    error: actionCount >= maxActions ? 'Max actions reached' : 'Timeout reached'
  };
}
