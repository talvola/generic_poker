/**
 * E2E Test Helpers for Table Operations
 *
 * Reusable helper functions for table-related E2E test operations.
 * These helpers abstract common operations like creating tables, joining,
 * taking seats, and cleaning up test state.
 */

import { Page, expect } from '@playwright/test';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const BASE_URL = 'http://localhost:5000';
export const DB_PATH = '/home/erik/generic_poker/instance/poker_platform.db';

// ============================================================================
// TABLE CREATION
// ============================================================================

export interface TableConfig {
  name?: string;
  variant?: string;
  bettingStructure?: string;
  smallBlind?: number;
  bigBlind?: number;
  minBuyIn?: number;
  maxBuyIn?: number;
  maxPlayers?: number;
}

const DEFAULT_TABLE_CONFIG: TableConfig = {
  variant: 'hold_em',
  bettingStructure: 'No-Limit',
  smallBlind: 1,
  bigBlind: 2,
  minBuyIn: 40,
  maxBuyIn: 200,
  maxPlayers: 9
};

/**
 * Create a new table with unique name.
 * Returns the table name and navigates to the table page.
 */
export async function createTable(page: Page, config: TableConfig = {}): Promise<string> {
  const finalConfig = { ...DEFAULT_TABLE_CONFIG, ...config };
  const tableName = config.name || `Test Table ${Date.now()}`;

  await page.goto(BASE_URL);

  // Wait for lobby to load - use specific button ID
  await expect(page.locator('#create-table-btn')).toBeVisible({ timeout: 10000 });

  // Click Create Table button
  await page.click('#create-table-btn');

  // Wait for create table modal to be visible (has 'show' class)
  const modal = page.locator('#create-table-modal.show');
  await expect(modal).toBeVisible({ timeout: 5000 });

  // Fill in table details - use correct form field names from lobby.html
  await page.fill('#table-name', tableName);

  if (finalConfig.variant) {
    await page.selectOption('#game-variant', finalConfig.variant);
  }

  if (finalConfig.maxPlayers) {
    await page.selectOption('#max-players', finalConfig.maxPlayers.toString());
  }

  if (finalConfig.bettingStructure) {
    // Map config value to actual option value
    const structureMap: Record<string, string> = {
      'No-Limit': 'no-limit',
      'no-limit': 'no-limit',
      'Pot-Limit': 'pot-limit',
      'pot-limit': 'pot-limit',
      'Limit': 'limit',
      'limit': 'limit'
    };
    const structure = structureMap[finalConfig.bettingStructure] || finalConfig.bettingStructure.toLowerCase();
    await page.selectOption('#betting-structure', structure);
  }

  // Wait for stakes inputs to be generated (they're dynamic based on betting structure)
  await page.waitForSelector('#small-blind', { timeout: 5000 });

  // Set stakes
  if (finalConfig.smallBlind) {
    await page.fill('#small-blind', finalConfig.smallBlind.toString());
  }
  if (finalConfig.bigBlind) {
    await page.fill('#big-blind', finalConfig.bigBlind.toString());
  }

  // Click Create button in modal footer
  const createButton = page.locator('#create-table-modal .modal-footer button[type="submit"]');
  await expect(createButton).toBeVisible();

  // Set up navigation promise before clicking
  const navigationPromise = page.waitForURL(/\/table\//, { timeout: 15000 }).catch(() => null);

  await createButton.click();

  // Wait for navigation OR check for error notification
  const navigation = await navigationPromise;

  if (!navigation) {
    // Check if there's an error notification
    const errorNotification = page.locator('.notification.error, .notification-error');
    if (await errorNotification.isVisible({ timeout: 1000 }).catch(() => false)) {
      const errorText = await errorNotification.textContent();
      throw new Error(`Table creation failed: ${errorText}`);
    }

    // Check if we're still on the lobby - try to find the created table and join it
    const tableCard = page.locator('.table-card', { hasText: tableName });
    if (await tableCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Table was created but we weren't redirected - click Join
      const joinBtn = tableCard.locator('.join-table-btn, button:has-text("Join")');
      await joinBtn.click();

      // Wait for seat selection modal
      const seatModal = page.locator('#seat-selection-modal');
      await expect(seatModal).toBeVisible({ timeout: 10000 });

      // Click Join Table button
      const joinTableBtn = seatModal.locator('button:has-text("Join Table")');
      await joinTableBtn.click();

      // Wait for navigation to table
      await page.waitForURL(/\/table\//, { timeout: 15000 });
    } else {
      throw new Error('Table creation did not navigate and table card not found');
    }
  }

  // Wait for poker table to render
  await expect(page.locator('.poker-table')).toBeVisible({ timeout: 10000 });

  return tableName;
}

// ============================================================================
// TABLE JOINING
// ============================================================================

export interface JoinConfig {
  buyIn?: number;
  seatNumber?: number | 'auto';
}

const DEFAULT_JOIN_CONFIG: JoinConfig = {
  buyIn: 80,
  seatNumber: 'auto'
};

/**
 * Join an existing table from the lobby by name.
 * Navigates to lobby, finds table, and completes join flow.
 */
export async function joinTableByName(
  page: Page,
  tableName: string,
  config: JoinConfig = {}
): Promise<void> {
  const finalConfig = { ...DEFAULT_JOIN_CONFIG, ...config };

  await page.goto(BASE_URL);

  // Wait for tables to load
  await expect(page.locator('.table-card').first()).toBeVisible({ timeout: 10000 });

  // Find the table card
  const tableCard = page.locator('.table-card', { hasText: tableName });
  await expect(tableCard).toBeVisible({ timeout: 5000 });

  const joinBtn = tableCard.locator('.join-table-btn');
  await expect(joinBtn).toBeVisible();

  // Click join button
  await joinBtn.click();

  // Wait for seat selection modal
  const seatModal = page.locator('#seat-selection-modal');
  await expect(seatModal).toBeVisible({ timeout: 10000 });

  // Set buy-in amount if input exists
  const buyInInput = seatModal.locator('input[name="buy-in-amount"], #buy-in-amount');
  if (await buyInInput.isVisible() && finalConfig.buyIn) {
    await buyInInput.fill(finalConfig.buyIn.toString());
  }

  // Select seat if specified
  if (finalConfig.seatNumber && finalConfig.seatNumber !== 'auto') {
    const seatRadio = seatModal.locator(`input[name="seat-choice"][value="${finalConfig.seatNumber}"]`);
    if (await seatRadio.isVisible()) {
      await seatRadio.click();
    }
  }

  // Click Join Table button
  const joinTableBtn = seatModal.locator('.modal-footer button:has-text("Join Table")');
  await expect(joinTableBtn).toBeVisible();
  await joinTableBtn.click();

  // Wait for navigation to table page
  await page.waitForURL(/\/table\//, { timeout: 15000 });

  // Wait for poker table to render
  await expect(page.locator('.poker-table')).toBeVisible({ timeout: 10000 });
}

/**
 * Join a table using the table URL directly.
 * Assumes user is already logged in and has access.
 */
export async function joinTableByUrl(page: Page, tableUrl: string): Promise<void> {
  await page.goto(tableUrl);
  await expect(page.locator('.poker-table')).toBeVisible({ timeout: 10000 });
}

/**
 * Get the current table URL from a page that's on a table.
 */
export function getTableUrl(page: Page): string {
  return page.url();
}

/**
 * Get the table ID from a table page URL.
 */
export function getTableIdFromUrl(url: string): string | null {
  const match = url.match(/\/table\/([a-f0-9-]+)/);
  return match ? match[1] : null;
}

// ============================================================================
// GAME ACTIONS
// ============================================================================

/**
 * Click the Ready button to indicate player is ready to start.
 * Waits for the ready panel to be visible first.
 */
export async function clickReady(page: Page): Promise<void> {
  // Wait for ready panel to be visible (game in waiting phase)
  const readyPanel = page.locator('#ready-panel:not(.hidden)');
  await expect(readyPanel).toBeVisible({ timeout: 15000 });

  const readyBtn = page.locator('#ready-btn');
  await expect(readyBtn).toBeVisible({ timeout: 5000 });
  await readyBtn.click();
}

/**
 * Wait for the game to start (cards dealt).
 */
export async function waitForGameStart(page: Page): Promise<void> {
  // Wait for hole cards to be visible
  await expect(page.locator('.player-cards .card, .hole-cards .card').first()).toBeVisible({
    timeout: 15000
  });
}

/**
 * Check if it's this player's turn to act.
 */
export async function isMyTurn(page: Page): Promise<boolean> {
  const actionBtns = page.locator(
    '.action-btn:not([disabled]), ' +
    'button:has-text("Fold"):not([disabled]), ' +
    'button:has-text("Call"):not([disabled]), ' +
    'button:has-text("Check"):not([disabled])'
  );
  return (await actionBtns.count()) > 0;
}

/**
 * Perform a betting action.
 * Waits for the action button to be visible before clicking.
 */
export async function performAction(
  page: Page,
  action: 'fold' | 'call' | 'check' | 'raise' | 'bet',
  amount?: number
): Promise<void> {
  // Wait for the button to be visible and enabled
  const buttonText = action === 'raise' ? 'Raise' : action === 'bet' ? 'Bet' : action.charAt(0).toUpperCase() + action.slice(1);
  const button = page.locator(`button:has-text("${buttonText}"):not([disabled])`);

  // Wait for button to be actionable
  await expect(button).toBeVisible({ timeout: 5000 });

  switch (action) {
    case 'fold':
    case 'call':
    case 'check':
      await button.click();
      break;
    case 'raise':
    case 'bet':
      if (amount) {
        const amountInput = page.locator('input[name="raise-amount"], input[name="bet-amount"], #bet-slider');
        if (await amountInput.isVisible()) {
          await amountInput.fill(amount.toString());
        }
      }
      await button.click();
      break;
  }

  // Wait briefly for WebSocket update to propagate
  await page.waitForTimeout(500);
}

// ============================================================================
// GAME STATE QUERIES
// ============================================================================

/**
 * Get the pot amount from the UI.
 */
export async function getPotAmount(page: Page): Promise<number> {
  const potText = await page.locator('.pot-amount').textContent();
  const match = potText?.match(/\$?(\d+)/);
  return match ? parseInt(match[1]) : 0;
}

/**
 * Get the count of community cards.
 * Cards are inside .card-slot elements with has-card class.
 */
export async function getCommunityCardCount(page: Page): Promise<number> {
  // Community cards are rendered inside card-slot elements
  return await page.locator('.card-slot.has-card .card, .community-cards .card').count();
}

/**
 * Get the player's chip stack.
 */
export async function getChipStack(page: Page, username?: string): Promise<number> {
  let stackLocator;
  if (username) {
    stackLocator = page.locator(`.player-info:has-text("${username}") .chip-stack, .seat:has-text("${username}") .chip-stack`);
  } else {
    // Get current player's stack
    stackLocator = page.locator('.current-player .chip-stack, .player-self .chip-stack');
  }

  const text = await stackLocator.first().textContent();
  const match = text?.match(/\$?(\d+)/);
  return match ? parseInt(match[1]) : 0;
}

/**
 * Check if a player is visible at the table.
 */
export async function isPlayerVisible(page: Page, username: string): Promise<boolean> {
  const playerName = page.locator(`.player-name:has-text("${username}")`);
  return await playerName.isVisible();
}

// ============================================================================
// CLEANUP AND TEST UTILITIES
// ============================================================================

/**
 * Clean up all test data from the database.
 * Removes all non-seed tables and their associated records.
 */
export async function cleanupTestTables(): Promise<void> {
  try {
    // Delete table_access records for test tables
    await execAsync(
      `sqlite3 ${DB_PATH} "DELETE FROM table_access WHERE table_id IN (SELECT id FROM poker_tables WHERE name LIKE 'Test %')"`
    );

    // Delete test tables
    await execAsync(
      `sqlite3 ${DB_PATH} "DELETE FROM poker_tables WHERE name LIKE 'Test %'"`
    );
  } catch (e) {
    console.error('Cleanup error:', e);
  }
}

/**
 * Clean up table_access records for a specific table.
 */
export async function cleanupTableAccess(tableId: string): Promise<void> {
  try {
    await execAsync(
      `sqlite3 ${DB_PATH} "DELETE FROM table_access WHERE table_id='${tableId}'"`
    );
  } catch (e) {
    console.error('Cleanup error:', e);
  }
}

/**
 * Call the test cleanup API endpoint.
 * This resets game sessions on the server.
 */
export async function callCleanupApi(page: Page): Promise<void> {
  try {
    await page.request.post(`${BASE_URL}/api/test/cleanup`);
  } catch (e) {
    // Endpoint might not exist yet
  }
}

/**
 * Get the table ID for a table by name.
 */
export async function getTableIdByName(tableName: string): Promise<string | null> {
  try {
    const { stdout } = await execAsync(
      `sqlite3 ${DB_PATH} "SELECT id FROM poker_tables WHERE name='${tableName.replace(/'/g, "''")}' LIMIT 1"`
    );
    return stdout.trim() || null;
  } catch (e) {
    return null;
  }
}
