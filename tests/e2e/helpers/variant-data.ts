/**
 * Variant test configuration data for parametrized E2E tests.
 *
 * 15 representative variants covering every interaction pattern:
 * betting-only, bring-in, draw, discard, expose, separate, declare, choose,
 * and various community card layouts (linear, multi-row, branching, grid).
 */

export interface VariantTestConfig {
  variant: string;           // Config file stem: 'hold_em', '5_card_draw'
  displayName: string;       // Test title: "Texas Hold'em"
  category: string;          // 'Hold\'em', 'Draw', 'Stud', etc.
  bettingStructure: 'No-Limit' | 'Pot-Limit' | 'Limit';
  forcedBetStyle: 'blinds' | 'bring-in';
  maxPlayers?: number;       // Default 6
}

/**
 * Tier 1: 15 representative variants for smoke testing.
 * Each variant covers a unique combination of action types and layouts.
 */
export const TIER_1_VARIANTS: VariantTestConfig[] = [
  // --- Betting-only (3 structures) ---
  {
    variant: 'hold_em',
    displayName: "Texas Hold'em",
    category: "Hold'em",
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'omaha',
    displayName: 'Omaha',
    category: 'Omaha',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'omaha_8',
    displayName: 'Omaha Hi-Lo',
    category: 'Omaha',
    bettingStructure: 'Pot-Limit',
    forcedBetStyle: 'blinds',
  },

  // --- Stud / bring-in ---
  {
    variant: '7_card_stud',
    displayName: '7-Card Stud',
    category: 'Stud',
    bettingStructure: 'Limit',
    forcedBetStyle: 'bring-in',
  },

  // --- Draw ---
  {
    variant: '5_card_draw',
    displayName: '5-Card Draw',
    category: 'Draw',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
    maxPlayers: 6,
  },
  {
    variant: 'badugi',
    displayName: 'Badugi',
    category: 'Draw',
    bettingStructure: 'Limit',
    forcedBetStyle: 'blinds',
  },

  // --- Pineapple (discard) ---
  {
    variant: 'crazy_pineapple',
    displayName: 'Crazy Pineapple',
    category: 'Pineapple',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },

  // --- Special actions ---
  {
    variant: 'showmaha',
    displayName: 'Showmaha',
    category: 'Other',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'sohe',
    displayName: 'SOHE',
    category: 'Other',
    bettingStructure: 'Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'straight_declare',
    displayName: 'Straight Poker Declare',
    category: 'Straight',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'paradise_road_pickem',
    displayName: "Paradise Road Pick'em",
    category: 'Other',
    bettingStructure: 'Limit',
    forcedBetStyle: 'blinds',
    maxPlayers: 2,
  },

  // --- Community card layouts ---
  {
    variant: 'double_board_hold_em',
    displayName: "Double Board Hold'em",
    category: "Hold'em",
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'chowaha',
    displayName: 'Chowaha',
    category: 'Community',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
  {
    variant: 'tic_tac_holdem',
    displayName: "Tic-Tac Hold'em",
    category: 'Community',
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },

  // --- Special deck ---
  {
    variant: 'six_plus_texas_hold_em',
    displayName: "Six Plus Hold'em",
    category: "Hold'em",
    bettingStructure: 'No-Limit',
    forcedBetStyle: 'blinds',
  },
];
