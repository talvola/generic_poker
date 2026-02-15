/**
 * E2E Test Helpers for Game Actions
 *
 * Reusable helper functions for N-player game flow.
 */

import { Page } from '@playwright/test';
import { isMyTurn } from './table-helpers';

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
 * Determine which player is the current actor (has enabled action buttons).
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
